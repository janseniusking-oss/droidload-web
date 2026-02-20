from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import requests
import re
import io
from urllib.parse import urlparse

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.tiktok.com/",
}

def extract_tiktok_video_url(shared_url: str) -> str | None:
    """Récupère l'URL vidéo propre depuis un lien TikTok (mobile ou web)"""
    try:
        # Suivre les redirections (très important pour les liens courts t.co / vm.tiktok)
        r = requests.get(shared_url, headers=HEADERS, allow_redirects=True, timeout=12)
        final_url = r.url

        # Cas lien mobile → on cherche la vidéo ID
        if "tiktok.com/@username/video/" in final_url:
            return final_url

        # Sinon on essaie de parser le HTML pour trouver le json ld+json ou le video id
        html = r.text
        match = re.search(r'"downloadAddr":"(https?://[^"]+)"', html) or \
                re.search(r'"playAddr":"(https?://[^"]+)"', html) or \
                re.search(r'/video/(\d+)', final_url)

        if match:
            if match.group(0).startswith("http"):
                return match.group(1)
            else:
                video_id = match.group(1)
                return f"https://www.tiktok.com/@user/video/{video_id}"

        return None
    except Exception:
        return None


def get_tiktok_no_watermark_url(video_page_url: str) -> tuple | None:
    """
    Méthode 1 : plusieurs services publics (souvent bloqués ou limités)
    Retourne (url_sans_watermark, type("video"/"image"), filename)
    """
    services = [
        # snaptik méthode (souvent marche encore en 2025-2026)
        {
            "url": "https://snaptik.app/abc.php",
            "method": "POST",
            "data": {"url": video_page_url},
            "regex": r'href="(https?://[^"]+)"[^>]*download-without-watermark'
        },
        # ssstik méthode
        {
            "url": "https://ssstik.io/abc?url=dl",
            "method": "POST",
            "data": {"id": video_page_url, "locale": "en", "tt": "0"},
            "regex": r'href="(https?[^"]+)"[^>]*without watermark'
        },
    ]

    for svc in services:
        try:
            if svc["method"] == "POST":
                r = requests.post(svc["url"], data=svc["data"], headers=HEADERS, timeout=15)
            else:
                r = requests.get(svc["url"] + "?url=" + video_page_url, headers=HEADERS, timeout=15)

            if r.status_code != 200:
                continue

            match = re.search(svc["regex"], r.text, re.IGNORECASE | re.DOTALL)
            if match:
                dl_url = match.group(1)
                # Déterminer type
                content_type = requests.head(dl_url, headers=HEADERS, timeout=8).headers.get("content-type", "")
                ext = "mp4" if "video" in content_type else "jpg" if "image" in content_type else "mp4"
                filename = f"tiktok_{video_page_url.split('/')[-1]}.{ext}"
                return dl_url, ext, filename

        except Exception:
            continue

    return None, None, None


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        tiktok_url = request.form.get("url", "").strip()

        if not tiktok_url:
            return render_template("index.html", error="Entre un lien TikTok stp")

        clean_url = extract_tiktok_video_url(tiktok_url)
        if not clean_url:
            return render_template("index.html", error="Lien TikTok invalide ou non reconnu")

        no_wm_url, media_type, filename = get_tiktok_no_watermark_url(clean_url)

        if not no_wm_url:
            return render_template("index.html", error="Impossible de trouver la version sans logo 😕 (TikTok a peut-être bloqué)")

        # On redirige directement vers le téléchargement
        return redirect(no_wm_url)

        # Alternative : montrer la page avec bouton de téléchargement
        # return render_template("index.html", success=True, download_url=no_wm_url, filename=filename, media_type=media_type)

    return render_template("index.html")


@app.route("/download")
def download():
    url = request.args.get("url")
    filename = request.args.get("filename", "tiktok_video.mp4")

    if not url:
        return "Pas d'URL", 400

    try:
        r = requests.get(url, headers=HEADERS, stream=True, timeout=20)
        r.raise_for_status()

        return send_file(
            io.BytesIO(r.content),
            as_attachment=True,
            download_name=filename,
            mimetype=r.headers.get("content-type", "video/mp4")
        )
    except Exception as e:
        return f"Erreur pendant le téléchargement : {str(e)}", 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
