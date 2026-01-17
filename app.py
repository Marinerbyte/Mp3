import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Fake Browser Header taaki block na ho
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
}

@app.route('/')
def home():
    return "✅ Music Direct Link Server is Running!", 200

@app.route('/convert', methods=['POST'])
def get_direct_link():
    try:
        data = request.json
        query = data.get('query')
        if not query: return jsonify({"error": "No query"}), 400

        # 1. JioSaavn Search API
        api_url = f"https://jiosaavn-api-io.vercel.app/search/songs?query={query}&limit=1"
        r = requests.get(api_url, headers=HEADERS, timeout=10, verify=False)
        res = r.json()

        if not res.get('success') or not res['data']['results']:
            return jsonify({"success": False, "error": "Song not found"}), 404

        song = res['data']['results'][0]
        
        # 2. HD Audio Link Extraction (320kbps)
        audio_url = None
        for q in song['downloadUrl']:
            if q['quality'] == '320kbps':
                audio_url = q['url']
                break
        if not audio_url: audio_url = song['downloadUrl'][-1]['url']

        # 3. Best Image Link
        image_url = song['image'][-1]['url'] if song['image'] else ""

        # Seedha Link wapas bhej do
        return jsonify({
            "success": True,
            "title": song['name'],
            "audio_url": audio_url, # Direct JioSaavn Link
            "card_url": image_url,  # Direct JioSaavn Cover
            "duration": str(song['duration'])
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
