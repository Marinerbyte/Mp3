import requests
import re
import urllib.parse
from flask import Flask, request, jsonify

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
}

@app.route('/')
def home():
    return "✅ YouTube Direct Streamer is Running!", 200

@app.route('/convert', methods=['POST'])
def convert_yt():
    try:
        data = request.json
        query = data.get('query')
        if not query: return jsonify({"error": "No query"}), 400

        # 1. Search YouTube for Video ID (Wahi logic jo Termux me chala)
        search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        res = requests.get(search_url, headers=HEADERS, timeout=10)
        video_ids = re.findall(r"watch\?v=(\S{11})", res.text)
        
        if not video_ids:
            return jsonify({"success": False, "error": "Song not found on YT"}), 404
        
        vid = video_ids[0]
        yt_url = f"https://www.youtube.com/watch?v={vid}"

        # 2. GET DIRECT MP3 LINK (Using Cobalt API - Sabse Fast)
        # Ye API humein seedha download link degi
        cobalt_api = "https://api.cobalt.tools/api/json"
        payload = {
            "url": yt_url,
            "downloadMode": "audio",
            "audioFormat": "mp3",
            "audioBitrate": "320"
        }
        c_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        c_res = requests.post(cobalt_api, json=payload, headers=c_headers, timeout=20)
        c_data = c_res.json()

        if c_data.get('status') == 'error':
            return jsonify({"success": False, "error": "Streaming Server Busy"}), 500

        direct_mp3_url = c_data.get('url')
        # Title clean karne ke liye (Optional)
        title = query.title()

        # 3. Return Data
        return jsonify({
            "success": True,
            "title": title,
            "audio_url": direct_mp3_url,
            "card_url": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg" # YT Thumbnail
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
