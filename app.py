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

# /tmp linux containers ke liye best hota hai (RAM disk jaisa fast)
DOWNLOAD_DIR = "/tmp/downloads"

# --- 🧹 LAYER 1: STARTUP CLEANUP ---
# Server on hote hi purana folder uda ke naya banao
if os.path.exists(DOWNLOAD_DIR):
    shutil.rmtree(DOWNLOAD_DIR)
os.makedirs(DOWNLOAD_DIR)

# --- 🧹 LAYER 2: WATCHDOG (BACKGROUND CLEANER) ---
def cleaner_watchdog():
    """Ye har 5 minute mein check karega aur 10 min purani files uda dega"""
    print("🧹 Cleaner Watchdog Started...")
    while True:
        try:
            time.sleep(300) # 5 Minute Sona
            
            now = time.time()
            cutoff = now - 600 # 10 Minute purana time
            
            if os.path.exists(DOWNLOAD_DIR):
                for filename in os.listdir(DOWNLOAD_DIR):
                    file_path = os.path.join(DOWNLOAD_DIR, filename)
                    # Check creation time
                    if os.path.getmtime(file_path) < cutoff:
                        try:
                            os.remove(file_path)
                            print(f"🗑️ Watchdog Deleted Old File: {filename}")
                        except Exception as e:
                            print(f"Error deleting {filename}: {e}")
        except Exception as e:
            print(f"Watchdog Error: {e}")

# Thread start karo (Daemon taaki main app ke sath band ho jaye)
t = threading.Thread(target=cleaner_watchdog, daemon=True)
t.start()

# --- HELPER: CATBOX UPLOAD ---
def upload_to_catbox(file_path=None, image_obj=None, is_image=False):
    try:
        url = "https://catbox.moe/user/api.php"
        buf = None
        files = {}
        
        if is_image and image_obj:
            buf = io.BytesIO()
            image_obj.save(buf, format='PNG')
            buf.seek(0)
            filename = f"card_{uuid.uuid4().hex}.png"
            files = {'reqtype': (None, 'fileupload'), 'fileToUpload': (filename, buf, 'image/png')}
        elif file_path:
            f = open(file_path, 'rb')
            filename = f"audio_{uuid.uuid4().hex}.mp3"
            files = {'reqtype': (None, 'fileupload'), 'fileToUpload': (filename, f)}
        
        r = requests.post(url, files=files, headers={'Connection': 'close'}, timeout=120)
        
        if file_path and 'f' in locals(): f.close()
        
        if r.status_code == 200 and "http" in r.text:
            return r.text.strip()
    except Exception as e:
        print(f"Upload Error: {e}")
    return None

# --- HELPER: DRAW CARD ---
def create_card(title, duration, thumb_url):
    try:
        w, h = 600, 300
        img = Image.new('RGB', (w, h), (17, 24, 39))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0,0,w,h], fill=(17, 24, 39))
        
        if thumb_url:
            try:
                resp = requests.get(thumb_url, timeout=5)
                with Image.open(io.BytesIO(resp.content)) as av:
                    av = av.resize((200, 200))
                    img.paste(av, (30, 50))
            except: pass

        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        except: font = ImageFont.load_default()
        
        title_text = title[:20] + "..." if len(title) > 20 else title
        draw.text((260, 80), title_text, font=font, fill="white")
        draw.text((260, 130), f"Time: {duration}", font=font, fill="cyan")
        
        return img
    except: return None

# --- API ENDPOINT ---
@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    query = data.get('query')
    
    if not query: return jsonify({"error": "No query"}), 400
    
    # Unique Temp ID taaki files mix na ho
    temp_id = uuid.uuid4().hex
    mp3_file = None
    
    try:
        # 1. Download
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{DOWNLOAD_DIR}/{temp_id}_%(id)s.%(ext)s',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
            'quiet': True, 'no_warnings': True, 'noplaylist': True
        }
        
        info = None
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if not query.startswith("http"): query = f"ytsearch:{query}"
            info = ydl.extract_info(query, download=True)
            if 'entries' in info: info = info['entries'][0]
            
            # Find the file we just downloaded
            # (Glob use kar rahe hain kyunki exact naam kabhi kabhi change ho jata hai)
            files = glob.glob(f"{DOWNLOAD_DIR}/{temp_id}*.mp3")
            if files: mp3_file = files[0]

        if not mp3_file: return jsonify({"error": "Download failed"}), 500

        # 2. Upload Audio
        audio_url = upload_to_catbox(file_path=mp3_file)
        
        # 3. Create & Upload Card
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
        return jsonify({"error": str(e)}), 500
    
    finally:
        # --- 🧹 LAYER 3: INSTANT CLEANUP ---
        # Request khatam hote hi file uda do, chahe error aaye ya success
        if mp3_file and os.path.exists(mp3_file):
            try:
                os.remove(mp3_file)
                print(f"✅ Cleaned up: {mp3_file}")
            except Exception as e:
                print(f"Cleanup Error: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
