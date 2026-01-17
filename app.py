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

# --- CONFIG ---
DOWNLOAD_DIR = "/tmp/music"
if os.path.exists(DOWNLOAD_DIR): shutil.rmtree(DOWNLOAD_DIR)
os.makedirs(DOWNLOAD_DIR)

# --- HOME ROUTE (Browser check ke liye) ---
@app.route('/')
def home(): 
    return "✅ JioSaavn Audio Worker is Running!", 200

# --- WATCHDOG ---
def cleaner():
    while True:
        try:
            time.sleep(300)
            now = time.time()
            for f in os.listdir(DOWNLOAD_DIR):
                fp = os.path.join(DOWNLOAD_DIR, f)
                if os.path.getmtime(fp) < now - 600: os.remove(fp)
        except: pass
t = threading.Thread(target=cleaner, daemon=True)
t.start()

# --- JIOSAAVN SEARCH ---
def search_jiosaavn(query):
    try:
        api_url = f"https://saavn.dev/api/search/songs?query={query}&limit=1"
        r = requests.get(api_url, timeout=10)
        data = r.json()
        
        if data['success'] and data['data']['results']:
            song = data['data']['results'][0]
            
            # Image
            image_url = song['image'][-1]['url']
            
            # Audio
            download_url = None
            for q in song['downloadUrl']:
                if q['quality'] == '320kbps': 
                    download_url = q['url']
                    break
            if not download_url: 
                download_url = song['downloadUrl'][-1]['url']

            return {
                'id': song['id'],
                'title': song['name'],
                'duration': song['duration'],
                'image': image_url,
                'url': download_url
            }
    except: pass
    return None

# --- UPLOAD HELPER ---
def upload_catbox(file_path=None, img_obj=None):
    try:
        url = "https://catbox.moe/user/api.php"
        files = {}
        if img_obj:
            buf = io.BytesIO()
            img_obj.save(buf, format='PNG')
            buf.seek(0)
            files = {'reqtype':(None,'fileupload'), 'fileToUpload':(f"c_{uuid.uuid4().hex}.png", buf, 'image/png')}
        elif file_path:
            f = open(file_path, 'rb')
            files = {'reqtype':(None,'fileupload'), 'fileToUpload':(f"s_{uuid.uuid4().hex}.mp3", f)}
        
        r = requests.post(url, files=files, headers={'Connection':'close'}, timeout=60)
        if file_path and 'f' in locals(): f.close()
        return r.text.strip() if r.status_code==200 else None
    except: return None

# --- CARD MAKER ---
def create_card(title, duration_sec, thumb_url):
    try:
        img = Image.new('RGB', (600, 300), (17, 24, 39))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0,0,600,300], fill=(17, 24, 39))
        
        if thumb_url:
            try:
                r = requests.get(thumb_url, timeout=5)
                with Image.open(io.BytesIO(r.content)) as av:
                    img.paste(av.resize((200,200)), (30,50))
            except: pass
            
        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        except: font = ImageFont.load_default()
        
        mins, secs = divmod(int(duration_sec), 60)
        
        draw.text((260, 80), title[:20]+"...", font=font, fill="white")
        draw.text((260, 130), f"Time: {mins}:{secs:02d}", font=font, fill="#2bc5b4")
        return img
    except: return None

# --- 👇 MAIN ENDPOINT (Iska hona zaroori hai) 👇 ---
@app.route('/convert', methods=['POST'])
def process():
    data = request.json
    query = data.get('query')
    if not query: return jsonify({"error": "No query"}), 400
    
    mp3_path = None
    try:
        # 1. Search
        info = search_jiosaavn(query)
        if not info: return jsonify({"error": "Song not found"}), 404
        
        # 2. Download
        mp3_path = f"{DOWNLOAD_DIR}/{info['id']}.mp3"
        with requests.get(info['url'], stream=True, timeout=20) as r:
            r.raise_for_status()
            with open(mp3_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                
        # 3. Upload
        audio_url = upload_catbox(file_path=mp3_path)
        if not audio_url: return jsonify({"error": "Upload failed"}), 500
        
        # 4. Card
        card_img = create_card(info['title'], info['duration'], info['image'])
        card_url = upload_catbox(img_obj=card_img)
        
        return jsonify({
            "success": True,
            "title": info['title'],
            "audio_url": audio_url,
            "card_url": card_url
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if mp3_path and os.path.exists(mp3_path):
            try: os.remove(mp3_path)
            except: pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
