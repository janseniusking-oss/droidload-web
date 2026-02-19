from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    video_url = request.json.get('url')
    # Ici on appelle l'API Cobalt depuis le serveur (pas de blocage CORS)
    response = requests.post("https://api.cobalt.tools/api/json", 
                             json={"url": video_url},
                             headers={"Accept": "application/json"})
    return jsonify(response.json())

if __name__ == '__main__':
    app.run(debug=True)
