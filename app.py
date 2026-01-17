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

# --- CONFIGURATION ---
# Linux containers (Render) ke liye /tmp sabse best aur fast hai
DOWNLOAD_DIR = "/tmp/downloads"

# --- 1. STARTUP CLEANUP ---
# Server start hote hi purana kachra saaf
if os.path.exists(DOWNLOAD_DIR):
    try:
        shutil.rmtree(DOWNLOAD_DIR)
    except: pass
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- 2. HOME ROUTE (Server Health Check) ---
@app.route('/')
def home():
    return "✅ Audio Worker is Running! (IPv4 Forced + Auto Clean)", 200

# --- 3. WATCHDOG (Background Safai Karamchari) ---
def cleaner_watchdog():
    """Har 5 minute mein check karega aur 10 minute purani files uda dega"""
    print("🧹 Cleaner Watchdog Started...")
    while True:
        try:
            time.sleep(300) # 5 Minute Wait
            now = time.time()
            if os.path.exists(DOWNLOAD_DIR):
                for f in os.listdir(DOWNLOAD_DIR):
                    fp = os.path.join(DOWNLOAD_DIR, f)
                    # Agar file 10 minute (600s) se purani hai
                    if os.path.getmtime(fp) < now - 600:
                        try: os.remove(fp)
                        except: pass
        except: pass

# Daemon thread (Server band hone par ye bhi band ho jayega)
t = threading.Thread(target=cleaner_watchdog, daemon=True)
t.start()

# --- 4. CATBOX UPLOADER ---
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
            filename = f"a_{uuid.uuid4().hex}.mp3"
            files = {'reqtype': (None, 'fileupload'), 'fileToUpload': (filename, f)}
        
        # Connection: close lagana zaroori hai taaki socket block na ho
        r = requests.post(url, files=files, headers={'Connection': 'close'}, timeout=120)
        
        if file_path and 'f' in locals(): f.close()
        
        if r.status_code == 200 and "http" in r.text:
            return r.text.strip()
    except Exception as e:
        print(f"Upload Error: {e}")
    return None

# --- 5. CARD GENERATOR ---
def create_card(title, duration, thumb_url):
    try:
        w, h = 600, 300
        img = Image.new('RGB', (w, h), (17, 24, 39))
        draw = ImageDraw.Draw(img)
        
        # Background
        draw.rectangle([0,0,w,h], fill=(17, 24, 39))
        
        # Thumbnail Download & Paste
        if thumb_url:
            try:
                r = requests.get(thumb_url, timeout=5)
                if r.status_code == 200:
                    with Image.open(io.BytesIO(r.content)) as av:
                        av = av.resize((200, 200))
                        img.paste(av, (30, 50))
            except: pass

        # Fonts Setup
        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        except: font = ImageFont.load_default()
        
        # Text Drawing
        clean_title = title[:20] + "..." if len(title) > 20 else title
        draw.text((260, 80), clean_title, font=font, fill="white")
        draw.text((260, 130), f"Time: {duration}", font=font, fill="cyan")
        
        return img
    except: return None

# --- 6. MAIN CONVERT API ---
@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    query = data.get('query')
    
    if not query: return jsonify({"error": "No query provided"}), 400
    
    temp_id = uuid.uuid4().hex
    mp3_file = None
    
    try:
        # 🔥 ROBUST YT-DLP OPTIONS (Anti-Block)
        ydl_opts = {
            'format': 'bestaudio/best',
            # File name pattern
            'outtmpl': f'{DOWNLOAD_DIR}/{temp_id}_%(id)s.%(ext)s',
            # Convert to MP3 using FFmpeg
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
            # Silence output to keep logs clean
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            # Bypass Geo-restrictions
            'geo_bypass': True,
            # Render Fix: Force IPv4 (IPv6 Google block karta hai)
            'source_address': '0.0.0.0', 
            # SSL Fix
            'nocheckcertificate': True
        }
        
        info = None
        # Download Process
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if not query.startswith("http"): query = f"ytsearch1:{query}"
            info = ydl.extract_info(query, download=True)
            if 'entries' in info: info = info['entries'][0]
            
            # Downloaded file dhoondo
            files = glob.glob(f"{DOWNLOAD_DIR}/{temp_id}*.mp3")
            if files: mp3_file = files[0]

        if not mp3_file: 
            return jsonify({"error": "Download failed (File not created)"}), 500

        # Upload Audio
        audio_url = upload_to_catbox(file_path=mp3_file)
        if not audio_url:
            return jsonify({"error": "Audio Upload Failed"}), 500
        
        # Create & Upload Card
        card_img = create_card(info.get('title'), info.get('duration_string'), info.get('thumbnail'))
        card_url = upload_to_catbox(image_obj=card_img, is_image=True)

        return jsonify({
            "success": True,
            "title": info.get('title'),
            "audio_url": audio_url,
            "card_url": card_url,
            "duration": info.get('duration_string')
        })

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return jsonify({"error": str(e)}), 500
    
    finally:
        # --- 7. INSTANT CLEANUP ---
        # Request khatam hote hi file delete karo
        if mp3_file and os.path.exists(mp3_file):
            try: os.remove(mp3_file)
            except: pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
