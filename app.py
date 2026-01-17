import requests
import urllib.parse
from flask import Flask, request, jsonify
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# --- CONFIGURATION ---
# Invidious Instances (YouTube Search Proxies)
SEARCH_INSTANCES = [
    "https://invidious.jing.rocks/api/v1/search",
    "https://inv.tux.pizza/api/v1/search",
    "https://invidious.drgns.space/api/v1/search"
]

# Cobalt Instances (YouTube to MP3 Engines)
COBALT_INSTANCES = [
    "https://cobalt.kwiatekmiki.pl/api/json",
    "https://cobalt.ducks.party/api/json",
    "https://api.cobalt.tools/api/json"
]

@app.route('/')
def home():
    return "✅ Music Engine v4.0 (High Reliability) is Running!", 200

@app.route('/convert', methods=['POST'])
def convert_logic():
    try:
        data = request.json
        query = data.get('query')
        if not query: return jsonify({"error": "No query"}), 400

        # --- STEP 1: SEARCH FOR VIDEO ID ---
        vid = None
        title = query
        for instance in SEARCH_INSTANCES:
            try:
                print(f"🔎 Searching on: {instance}")
                params = {"q": query, "type": "video"}
                r = requests.get(instance, params=params, timeout=10, verify=False)
                res = r.json()
                if res and len(res) > 0:
                    vid = res[0]['videoId']
                    title = res[0]['title']
                    break
            except: continue

        if not vid:
            return jsonify({"success": False, "error": "Search engines are down"}), 500

        yt_url = f"https://www.youtube.com/watch?v={vid}"
        print(f"✅ Found Video: {yt_url}")

        # --- STEP 2: GET MP3 LINK ---
        mp3_link = None
        payload = {
            "url": yt_url,
            "downloadMode": "audio",
            "audioFormat": "mp3",
            "audioBitrate": "320"
        }
        
        for c_node in COBALT_INSTANCES:
            try:
                print(f"🎵 Trying Cobalt: {c_node}")
                c_res = requests.post(c_node, json=payload, timeout=15, headers={"Accept": "application/json"})
                c_data = c_res.json()
                if 'url' in c_data:
                    mp3_link = c_data['url']
                    break
            except: continue

        if not mp3_link:
            return jsonify({"success": False, "error": "Streaming engines busy"}), 500

        # --- STEP 3: RETURN DATA ---
        return jsonify({
            "success": True,
            "title": title,
            "audio_url": mp3_link,
            "card_url": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
        })

    except Exception as e:
        return jsonify({"success": False, "error": f"Server Crash: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
