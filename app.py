from flask import Flask, render_template, request, jsonify, send_file
import requests
import re
import io
from urllib.parse import unquote

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.tiktok.com/",
    "Origin": "https://www.tiktok.com",
}

def get_clean_tiktok_url(shared_url: str) -> str | None:
    try:
        with requests.Session() as session:
            session.headers.update(HEADERS)
            resp = session.get(shared_url, allow_redirects=True, timeout=12)
            final_url = resp.url
            
            if "/video/" in final_url or "/t/" in final_url:
                return final_url
                
            # Si redirection vers page d'erreur TikTok
            if "unavailable" in final_url.lower() or "private" in final_url.lower():
                return None
                
            return final_url
    except Exception:
        return None


def extract_no_watermark_link(page_url: str) -> dict:
    services = [
        # SnapTik (souvent mis à jour)
        {
            "url": "https://snaptik.app/abc.php",
            "method": "POST",
            "data": {"url": page_url},
            "regex": r'(https?://[^"\']+\.mp4[^"\']*?)(?:"|\')(?=.*without.*watermark|.*no.*logo)'
        },
        # SnapTik alternative domain
        {
            "url": "https://snaptik.gd/abc.php",
            "method": "POST",
            "data": {"url": page_url},
            "regex": r'(https?://[^"\']+\.mp4[^"\']*?)(?:"|\')(?=.*without.*watermark|.*no.*logo)'
        },
        # SSSTik
        {
            "url": "https://ssstik.io/abc?url=dl",
            "method": "POST",
            "data": {"id": page_url, "locale": "en", "tt": "0"},
            "regex": r'href="(https?://[^"]+)"[^>]*?without watermark|no watermark|download'
        },
        # DLTTK / MusicallyDown style (2025-2026)
        {
            "url": "https://dl.tikdown.org/api/ajaxSearch",
            "method": "POST",
            "data": {"q": page_url},
            "regex": r'href="(https?://[^"]+\.mp4[^"]*)"[^>]*?download'
        },
        # Fallback : essayer de trouver playAddr directement dans le HTML TikTok
        {
            "url": page_url,
            "method": "GET",
            "data": {},
            "regex": r'"playAddr":\s*["\']?(https?://[^"\']+)["\']?|'
                     r'"downloadAddr":\s*["\']?(https?://[^"\']+)["\']?'
        }
    ]

    for svc in services:
        try:
            if svc["method"] == "POST":
                r = requests.post(svc["url"], data=svc["data"], headers=HEADERS, timeout=15)
            else:
                r = requests.get(svc["url"], headers=HEADERS, timeout=15)

            if r.status_code not in (200, 201, 202):
                continue

            matches = re.findall(svc["regex"], r.text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                if isinstance(match, tuple):
                    url_candidate = next((m for m in match if m), None)
                else:
                    url_candidate = match

                if url_candidate and "mp4" in url_candidate.lower():
                    clean_url = unquote(url_candidate.strip('"\''))
                    # Vérification minimale
                    try:
                        head = requests.head(clean_url, headers=HEADERS, timeout=8, allow_redirects=True)
                        if head.status_code in (200, 206) and "video" in head.headers.get("content-type", ""):
                            filename = f"tiktok_{page_url.split('/')[-1]}.mp4"
                            return {
                                "success": True,
                                "url": clean_url,
                                "filename": filename
                            }
                    except:
                        pass  # on continue si head échoue

        except Exception:
            continue

    return {
        "success": False,
        "message": "Impossible de trouver un lien sans filigrane. Vidéo privée, supprimée, ou restrictions régionales ?"
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/download", methods=["POST"])
def api_download():
    try:
        data = request.get_json(silent=True) or {}
        tiktok_url = (data.get("url") or "").strip()

        if not tiktok_url:
            return jsonify({
                "status": "error",
                "message": "Veuillez fournir un lien TikTok"
            }), 400

        clean_url = get_clean_tiktok_url(tiktok_url)
        if not clean_url:
            return jsonify({
                "status": "error",
                "message": "Lien TikTok invalide ou redirection échouée"
            }), 400

        result = extract_no_watermark_link(clean_url)

        if not result.get("success"):
            return jsonify({
                "status": "error",
                "message": result.get("message", "Échec de l'extraction du lien sans filigrane")
            }), 400

        return jsonify({
            "status": "success",
            "url": result["url"],
            "filename": result.get("filename", "video_tiktok.mp4")
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Erreur serveur : {str(e)}"
        }), 500


@app.route("/proxy-dl")
def proxy_download():
    url = request.args.get("url")
    if not url:
        return "Paramètre url manquant", 400

    try:
        r = requests.get(url, headers=HEADERS, stream=True, timeout=30)
        r.raise_for_status()

        filename = request.args.get("filename", "tiktok_video.mp4")

        return send_file(
            io.BytesIO(r.content),
            as_attachment=True,
            download_name=filename,
            mimetype="video/mp4"
        )
    except Exception as e:
        return f"Impossible de télécharger la vidéo : {str(e)}", 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
