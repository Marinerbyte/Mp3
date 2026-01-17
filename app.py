import os
import glob
import uuid
import requests
import yt_dlp
from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont
import io

app = Flask(__name__)

DOWNLOAD_DIR = "/tmp/downloads"
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

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
        
        # Fresh connection
        r = requests.post(url, files=files, headers={'Connection': 'close'}, timeout=60)
        
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
        
        # Gradient
        # (Simple solid color for speed on worker)
        draw.rectangle([0,0,w,h], fill=(17, 24, 39))
        
        # Thumbnail
        if thumb_url:
            try:
                resp = requests.get(thumb_url, timeout=5)
                with Image.open(io.BytesIO(resp.content)) as av:
                    av = av.resize((200, 200))
                    img.paste(av, (30, 50))
            except: pass

        # Font (Default load to avoid path issues)
        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        except: font = ImageFont.load_default()
        
        draw.text((260, 80), title[:25], font=font, fill="white")
        draw.text((260, 130), f"Time: {duration}", font=font, fill="cyan")
        
        return img
    except: return None

# --- API ENDPOINT ---
@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    query = data.get('query')
    
    if not query: return jsonify({"error": "No query"}), 400
    
    mp3_file = None
    try:
        # 1. Download
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{DOWNLOAD_DIR}/%(id)s.%(ext)s',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
            'quiet': True, 'no_warnings': True, 'noplaylist': True
        }
        
        info = None
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if not query.startswith("http"): query = f"ytsearch:{query}"
            info = ydl.extract_info(query, download=True)
            if 'entries' in info: info = info['entries'][0]
            
            file_id = info['id']
            files = glob.glob(f"{DOWNLOAD_DIR}/{file_id}*.mp3")
            if files: mp3_file = files[0]

        if not mp3_file: return jsonify({"error": "Download failed"}), 500

        # 2. Upload Audio
        audio_url = upload_to_catbox(file_path=mp3_file)
        
        # 3. Create & Upload Card
        card_img = create_card(info.get('title'), info.get('duration_string'), info.get('thumbnail'))
        card_url = upload_to_catbox(image_obj=card_img, is_image=True)

        # 4. Cleanup
        if os.path.exists(mp3_file): os.remove(mp3_file)

        return jsonify({
            "success": True,
            "title": info.get('title'),
            "audio_url": audio_url,
            "card_url": card_url,
            "duration": info.get('duration_string')
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
