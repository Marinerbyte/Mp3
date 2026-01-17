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

# --- BROWSER HEADERS (ZAROORI HAI BLOCK SE BACHNE KE LIYE) ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- HOME ROUTE ---
@app.route('/')
def home():
    return "✅ JioSaavn Worker is Running! (With Anti-Block Headers)", 200

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

# --- HELPER: SEARCH JIOSAAVN ---
def search_jiosaavn(query):
    try:
        # API request with Headers
        api_url = f"https://saavn.dev/api/search/songs?query={query}&limit=1"
        r = requests.get(api_url, headers=HEADERS, timeout=15)
        data = r.json()
        
        if not data['success'] or not data['data']['results']:
            return None, "Song not found in API"

        song = data['data']['results'][0]
        
        # Image Logic
        image_url = song['image'][-1]['url'] if song['image'] else ""
        
        # Audio Logic
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
        }, None
    except Exception as e:
        return None, str(e)

# --- HELPER: UPLOAD TO CATBOX ---
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
        
        # Headers yahan bhi zaroori hain
        r = requests.post(url, files=files, headers={'Connection':'close', 'User-Agent': HEADERS['User-Agent']}, timeout=120)
        
        if file_path and 'f' in locals(): f.close()
        
        if r.status_code == 200 and "http" in r.text:
            return r.text.strip()
    except Exception as e:
        print(f"Upload Err: {e}")
    return None

# --- CARD MAKER ---
def create_card(title, duration_sec, thumb_url):
    try:
        img = Image.new('RGB', (600, 300), (17, 24, 39))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0,0,600,300], fill=(17, 24, 39))
        
        if thumb_url:
            try:
                r = requests.get(thumb_url, headers=HEADERS, timeout=5)
                with Image.open(io.BytesIO(r.content)) as av:
                    img.paste(av.resize((200,200)), (30,50))
            except: pass
            
        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        except: font = ImageFont.load_default()
        
        try:
            mins, secs = divmod(int(duration_sec), 60)
            time_str = f"{mins}:{secs:02d}"
        except: time_str = "00:00"
        
        draw.text((260, 80), title[:20]+"...", font=font, fill="white")
        draw.text((260, 130), f"Time: {time_str}", font=font, fill="#2bc5b4")
        return img
    except: return None

# --- MAIN ENDPOINT ---
@app.route('/convert', methods=['POST'])
def process():
    try:
        data = request.json
        if not data or 'query' not in data:
            return jsonify({"error": "No query provided"}), 400
        
        query = data.get('query')
        
        # 1. Search (With Error Catching)
        info, err = search_jiosaavn(query)
        if err: return jsonify({"error": f"Search Failed: {err}"}), 500
        if not info: return jsonify({"error": "Song not found"}), 404
        
        # 2. Download
        mp3_path = f"{DOWNLOAD_DIR}/{info['id']}.mp3"
        try:
            with requests.get(info['url'], headers=HEADERS, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(mp3_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
        except Exception as e:
            return jsonify({"error": f"Download Failed: {str(e)}"}), 500
            
        # 3. Upload Audio
        audio_url = upload_catbox(file_path=mp3_path)
        if not audio_url: return jsonify({"error": "Catbox Upload Failed"}), 500
        
        # 4. Upload Card
        card_img = create_card(info['title'], info['duration'], info['image'])
        card_url = upload_catbox(img_obj=card_img)
        
        # 5. Cleanup
        if os.path.exists(mp3_path): os.remove(mp3_path)

        return jsonify({
            "success": True,
            "title": info['title'],
            "audio_url": audio_url,
            "card_url": card_url,
            "duration": str(info['duration'])
        })

    except Exception as e:
        return jsonify({"error": f"Internal Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
