from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/download', methods=['POST'])
def download():
    user_url = request.json.get('url')
    try:
        # On utilise l'API Cobalt spécialisée dans TikTok
        payload = {
            "url": user_url,
            "vQuality": "720",
            "isNoWatermark": True  # Option magique pour TikTok sans logo !
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        r = requests.post("https://api.cobalt.tools/api/json", json=payload, headers=headers)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
