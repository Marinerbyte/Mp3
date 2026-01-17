import os
import uuid
import requests
import time
import shutil
import threading
from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont
import io

app = Flask(__name__)

# --- CONFIGURATION ---
DOWNLOAD_DIR = "/tmp/music"

# Startup Cleanup
if os.path.exists(DOWNLOAD_DIR):
    shutil.rmtree(DOWNLOAD_DIR)
os.makedirs(DOWNLOAD_DIR)

@app.route('/')
def home():
    return "✅ JioSaavn Audio Worker is Running!", 200

# --- WATCHDOG (Safai) ---
def cleaner_watchdog():
    while True:
        try:
            time.sleep(300)
            now = time.time()
            if os.path.exists(DOWNLOAD_DIR):
                for f in os.listdir(DOWNLOAD_DIR):
                    fp = os.path.join(DOWNLOAD_DIR, f)
                    if os.path.getmtime(fp) < now - 600:
                        try: os.remove(fp)
                        except: pass
        except: pass

t = threading.Thread(target=cleaner_watchdog, daemon=True)
t.start()

# --- HELPER: SEARCH JIOSAAVN ---
def search_jiosaavn(query):
    try:
        # Public API Wrapper for JioSaavn
        api_url = f"https://saavn.dev/api/search/songs?query={query}&limit=1"
        r = requests.get(api_url, timeout=10)
        data = r.json()
        
        if data['success'] and data['data']['results']:
            song = data['data']['results'][0]
            
            # 1. Best Image Dhundo (500x500)
            image_url = song['image'][-1]['url'] # Last wala usually high quality hota hai
            
            # 2. Best Audio Dhundo (320kbps)
            download_url = None
            # API structure check karke best quality uthao
            for q in song['downloadUrl']:
                if q['quality'] == '320kbps': 
                    download_url = q['url']
                    break
            if not download_url: 
                download_url = song['downloadUrl'][-1]['url'] # Fallback to best available

            return {
                'id': song['id'],
                'title': song['name'],
                'duration': song['duration'], # Seconds
                'image': image_url,
                'url': download_url
            }
    except Exception as e:
        print(f"Jio API Error: {e}")
    return None

# --- HELPER: UPLOAD TO CATBOX ---
def upload_to_catbox(file_path=None, image_obj=None, is_image=False):
    try:
        url = "https://catbox.moe/user/api.php"
        files = {}
        
        if is_image and image_obj:
            buf = io.BytesIO()
            image_obj.save(buf, format='PNG')
            buf.seek(0)
            filename = f"c_{uuid.uuid4().hex}.png"
            files = {'reqtype': (None, 'fileupload'), 'fileToUpload': (filename, buf, 'image/png')}
        elif file_path:
            f = open(file_path, 'rb')
            filename = f"s_{uuid.uuid4().hex}.mp3"
            files = {'reqtype': (None, 'fileupload'), 'fileToUpload': (filename, f)}
        
        # Connection Close (Zaroori hai)
        r = requests.post(url, files=files, headers={'Connection': 'close'}, timeout=60)
        
        if file_path and 'f' in locals(): f.close()
        
        if r.status_code == 200 and "http" in r.text:
            return r.text.strip()
    except Exception as e:
        print(f"Upload Error: {e}")
    return None

# --- HELPER: CREATE CARD ---
def create_card(title, duration_sec, thumb_url):
    try:
        img = Image.new('RGB', (600, 300), (17, 24, 39))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0,0,600,300], fill=(17, 24, 39))
        
        if thumb_url:
            try:
                r = requests.get(thumb_url, timeout=5)
                with Image.open(io.BytesIO(r.content)) as av:
                    img.paste(av.resize((200, 200)), (30, 50))
            except: pass

        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        except: font = ImageFont.load_default()
        
        # Format Seconds to Min:Sec
        mins, secs = divmod(int(duration_sec), 60)
        time_str = f"{mins}:{secs:02d}"
        
        draw.text((260, 80), title[:20]+"...", font=font, fill="white")
        draw.text((260, 130), f"Time: {time_str}", font=font, fill="#2bc5b4") # Jio Green Color
        
        return img
    except: return None

# --- MAIN ENDPOINT ---
@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    query = data.get('query')
    if not query: return jsonify({"error": "No query"}), 400
    
    mp3_path = None
    
    try:
        # 1. Search Song
        info = search_jiosaavn(query)
        if not info: return jsonify({"error": "Song not found on JioSaavn"}), 404
        
        # 2. Download MP3 (Direct Stream Copy - Super Fast)
        mp3_path = f"{DOWNLOAD_DIR}/{info['id']}.mp3"
        
        with requests.get(info['url'], stream=True, timeout=20) as r:
            r.raise_for_status()
            with open(mp3_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        # 3. Upload Audio
        audio_url = upload_to_catbox(file_path=mp3_path)
        if not audio_url: return jsonify({"error": "Upload Failed"}), 500
        
        # 4. Create Card
        card_img = create_card(info['title'], info['duration'], info['image'])
        card_url = upload_to_catbox(image_obj=card_img, is_image=True)

        return jsonify({
            "success": True,
            "title": info['title'],
            "audio_url": audio_url,
            "card_url": card_url,
            "duration": str(info['duration'])
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    finally:
        # Cleanup
        if mp3_path and os.path.exists(mp3_path):
            try: os.remove(mp3_path)
            except: pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
