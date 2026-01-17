import os
import glob
import uuid
import requests
import yt_dlp
import time
import shutil
import threading
from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont
import io

app = Flask(__name__)

DOWNLOAD_DIR = "/tmp/downloads"
if os.path.exists(DOWNLOAD_DIR): shutil.rmtree(DOWNLOAD_DIR)
os.makedirs(DOWNLOAD_DIR)

@app.route('/')
def home(): return "✅ Audio Worker (iOS Mode) Running!", 200

# Watchdog
def cleaner_watchdog():
    while True:
        try:
            time.sleep(300)
            now = time.time()
            if os.path.exists(DOWNLOAD_DIR):
                for f in os.listdir(DOWNLOAD_DIR):
                    fp = os.path.join(DOWNLOAD_DIR, f)
                    if os.path.getmtime(fp) < now - 600: os.remove(fp)
        except: pass
t = threading.Thread(target=cleaner_watchdog, daemon=True)
t.start()

# Upload Helper
def upload_to_catbox(file_path=None, image_obj=None, is_image=False):
    try:
        url = "https://catbox.moe/user/api.php"
        files = {}
        if is_image and image_obj:
            buf = io.BytesIO()
            image_obj.save(buf, format='PNG')
            buf.seek(0)
            files = {'reqtype': (None, 'fileupload'), 'fileToUpload': (f"c_{uuid.uuid4().hex}.png", buf, 'image/png')}
        elif file_path:
            f = open(file_path, 'rb')
            files = {'reqtype': (None, 'fileupload'), 'fileToUpload': (f"a_{uuid.uuid4().hex}.mp3", f)}
        
        r = requests.post(url, files=files, headers={'Connection': 'close'}, timeout=120)
        if file_path and 'f' in locals(): f.close()
        return r.text.strip() if r.status_code == 200 else None
    except: return None

# Card Helper
def create_card(title, duration, thumb_url):
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
        draw.text((260, 80), title[:20]+"...", font=font, fill="white")
        draw.text((260, 130), f"Time: {duration}", font=font, fill="cyan")
        return img
    except: return None

@app.route('/convert', methods=['POST'])
def convert():
    try:
        data = request.json
        query = data.get('query')
        if not query: return jsonify({"error": "No query"}), 400
        
        temp_id = uuid.uuid4().hex
        mp3_file = None
        
        # 🔥 FINAL ANTI-BLOCK SETTINGS (iOS Client)
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{DOWNLOAD_DIR}/{temp_id}_%(id)s.%(ext)s',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
            # 👇 CHANGE IS HERE: iOS Client use kar rahe hain
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios'], 
                    'player_skip': ['webpage', 'configs', 'js'], 
                }
            },
            # 👇 IPv4 Force (Render par zaroori hai)
            'source_address': '0.0.0.0'
        }
        
        info = None
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if not query.startswith("http"): query = f"ytsearch1:{query}"
            info = ydl.extract_info(query, download=True)
            if 'entries' in info: info = info['entries'][0]
            
            files = glob.glob(f"{DOWNLOAD_DIR}/{temp_id}*.mp3")
            if files: mp3_file = files[0]

        if not mp3_file: return jsonify({"error": "Download Failed"}), 500

        audio_url = upload_to_catbox(file_path=mp3_file)
        card_img = create_card(info.get('title'), info.get('duration_string'), info.get('thumbnail'))
        card_url = upload_to_catbox(image_obj=card_img, is_image=True)

        return jsonify({
            "success": True,
            "title": info.get('title'),
            "audio_url": audio_url,
            "card_url": card_url
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    finally:
        if mp3_file and os.path.exists(mp3_file):
            try: os.remove(mp3_file)
            except: pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
