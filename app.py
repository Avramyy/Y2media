#!/usr/bin/env python3
"""
YouTube to MP3/MP4 Converter
Cross-platform web app that runs on PC and phone via browser.
"""

import os
import uuid
import time
import threading
import yt_dlp
from flask import Flask, render_template, request, jsonify, send_file, url_for

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB limit

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# In-memory job tracking
jobs = {}  # {job_id: {"status": "downloading"|"done"|"error", "progress": 0, "filepath": None, "error": None}}


def cleanup_old_files():
    """Remove downloaded files older than 30 minutes."""
    now = time.time()
    for fname in os.listdir(DOWNLOAD_DIR):
        fpath = os.path.join(DOWNLOAD_DIR, fname)
        if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > 1800:
            try:
                os.remove(fpath)
            except OSError:
                pass


def progress_hook(d, job_id):
    """yt-dlp progress callback — smooth 0-100% like official sites.

    Uses a simulated smooth progress that increases at a constant rate,
    independent of actual download speed. The bar moves smoothly from
    0% to 95% during download, then jumps to 100% when done.
    """
    if job_id not in jobs:
        return
    job = jobs[job_id]

    if d["status"] == "downloading":
        # Initialize on first callback
        if "_dl_start" not in job:
            job["_dl_start"] = time.time()
            # Estimate total time from file size + speed
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            speed = d.get("speed") or 0
            if total > 0 and speed > 0:
                # Real ETA — but ensure minimum 30 seconds for smooth bar
                est = max(total / speed, 30.0)
            else:
                est = 30.0  # default 30 seconds
            job["_dl_estimated"] = est

        elapsed = time.time() - job["_dl_start"]
        est = job.get("_dl_estimated", 20.0)

        # Smooth linear progress: 0% -> 95% over estimated time
        pct = int((elapsed / est) * 95)
        new_pct = min(pct, 95)

        # Never go backward
        if new_pct > job.get("progress", 0):
            job["progress"] = new_pct

    elif d["status"] == "finished":
        job["_dl_end"] = time.time()
        job["progress"] = 95
        job["status"] = "processing"


def do_download(url, fmt, quality, job_id):
    """Run download in a background thread."""
    try:
        unique = uuid.uuid4().hex[:10]
        output_template = os.path.join(DOWNLOAD_DIR, f"{unique}_%(title)s.%(ext)s")

        if fmt == "mp3":
            # Audio only
            audio_quality_map = {
                "128": "128",
                "192": "192",
                "256": "256",
                "320": "320",
            }
            audio_q = audio_quality_map.get(quality, "192")
            opts = {
                "format": "bestaudio/best",
                "outtmpl": output_template,
                "progress_hooks": [lambda d: progress_hook(d, job_id)],
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": audio_q,
                    }
                ],
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
            }
        else:
            # Video — split video+audio for maximum compatibility
            height_map = {"360": "360", "480": "480", "720": "720", "1080": "1080", "best": "best"}
            max_height = height_map.get(quality, "720")
            if max_height == "best":
                fmt_str = "bestvideo+bestaudio/best"
            else:
                fmt_str = (
                    f"bestvideo[height<={max_height}]+bestaudio"
                    f"/bestvideo[height<={max_height}]+bestaudio[ext=m4a]"
                    f"/best[height<={max_height}]/best"
                )
            opts = {
                "format": fmt_str,
                "merge_output_format": "mp4",
                "outtmpl": output_template,
                "progress_hooks": [lambda d: progress_hook(d, job_id)],
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
            }

        # Start smooth processing animation (95% -> 100%)
        def animate_processing():
            start = time.time()
            while jobs.get(job_id, {}).get("status") == "processing":
                elapsed = time.time() - start
                # Smoothly go from 95% to 100% over ~10 seconds
                pct = min(95 + int((elapsed / 10.0) * 5), 99)
                if job_id in jobs:
                    jobs[job_id]["progress"] = pct
                time.sleep(0.5)
        anim_thread = threading.Thread(target=animate_processing)
        anim_thread.daemon = True
        anim_thread.start()

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Find the downloaded file
        if info:
            ext = "mp3" if fmt == "mp3" else "mp4"
            title = info.get("title", "video")
            # Sanitize title for filename
            safe_title = "".join(c if c.isalnum() or c in " _-" else "" for c in title)[:60]
            final_name = f"{safe_title}.{ext}"
            final_path = os.path.join(DOWNLOAD_DIR, final_name)

            # Find the actual file (yt-dlp may name it differently)
            actual_file = None
            for fname in os.listdir(DOWNLOAD_DIR):
                if fname.startswith(unique):
                    actual_file = os.path.join(DOWNLOAD_DIR, fname)
                    break

            if actual_file and os.path.exists(actual_file):
                if actual_file != final_path:
                    # Remove existing file with same name
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    os.rename(actual_file, final_path)
                jobs[job_id]["filepath"] = final_path
                jobs[job_id]["filename"] = final_name
                jobs[job_id]["status"] = "done"
            else:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"] = "File not found after download"
        else:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = "Could not extract video info"

    except yt_dlp.utils.DownloadError as e:
        import re
        # Strip ANSI color codes from error message
        error_msg = re.sub(r'\x1b\[[0-9;]*m', '', str(e))
        # Provide friendly messages
        if "not available on this app" in error_msg.lower():
            error_msg = "This video is restricted by YouTube and cannot be downloaded."
        elif "Sign in" in error_msg or "login" in error_msg.lower():
            error_msg = "This video may be private or age-restricted and cannot be downloaded."
        elif "Private video" in error_msg:
            error_msg = "This video is private and cannot be downloaded."
        elif "Video unavailable" in error_msg:
            error_msg = "This video is unavailable."
        elif "Premiere" in error_msg:
            error_msg = "This video is a premiere and not yet available."
        elif "is live" in error_msg.lower():
            error_msg = "Live streams cannot be downloaded."
        else:
            # Clean up generic error - remove YouTube-specific prefixes
            error_msg = re.sub(r'\[youtube\]\s*\w+:\s*', '', error_msg)
            if len(error_msg) > 150:
                error_msg = error_msg[:150] + "..."
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = error_msg
    except Exception as e:
        import re
        error_msg = re.sub(r'\x1b\[[0-9;]*m', '', str(e))
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = f"Something went wrong. Try another video."


@app.route("/")
def index():
    cleanup_old_files()
    return render_template("index.html")


@app.route("/api/info", methods=["POST"])
def video_info():
    """Fetch video metadata (thumbnail, title, duration) without downloading."""
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    if not any(domain in url for domain in ["youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com"]):
        return jsonify({"error": "Not a YouTube URL"}), 400

    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return jsonify({"error": "Could not fetch video info"}), 404

        # Get best thumbnail
        thumbnail = info.get("thumbnail")
        if not thumbnail and info.get("thumbnails"):
            # Pick the highest res thumbnail
            thumbs = sorted(info["thumbnails"], key=lambda t: t.get("width", 0) * t.get("height", 0), reverse=True)
            thumbnail = thumbs[0].get("url") if thumbs else None

        duration = info.get("duration", 0)
        duration_str = ""
        if duration:
            m, s = divmod(int(duration), 60)
            h, m = divmod(m, 60)
            if h:
                duration_str = f"{h}:{m:02d}:{s:02d}"
            else:
                duration_str = f"{m}:{s:02d}"

        return jsonify({
            "title": info.get("title", ""),
            "thumbnail": thumbnail,
            "duration": duration_str,
            "channel": info.get("channel", info.get("uploader", "")),
        })

    except yt_dlp.utils.DownloadError:
        return jsonify({"error": "Video not found or unavailable"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.get_json()
    url = data.get("url", "").strip()
    fmt = data.get("format", "mp4")  # mp3 or mp4
    quality = data.get("quality", "720")

    if not url:
        return jsonify({"error": "Please enter a YouTube URL"}), 400

    # Basic URL validation
    if not any(domain in url for domain in ["youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com"]):
        return jsonify({"error": "This is not a YouTube link"}), 400

    if fmt not in ("mp3", "mp4"):
        return jsonify({"error": "Format must be mp3 or mp4"}), 400

    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {
        "status": "downloading",
        "progress": 0,
        "filepath": None,
        "filename": None,
        "error": None,
        "created": time.time(),
    }

    thread = threading.Thread(target=do_download, args=(url, fmt, quality, job_id))
    thread.daemon = True
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    resp = {
        "status": job["status"],
        "progress": job["progress"],
    }
    if job["status"] == "error":
        resp["error"] = job["error"]
    if job["status"] == "done":
        resp["filename"] = job.get("filename", "download")
    return jsonify(resp)


@app.route("/api/file/<job_id>")
def download_file(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "done" or not job.get("filepath"):
        return jsonify({"error": "File not ready"}), 404

    filepath = job["filepath"]
    if not os.path.exists(filepath):
        return jsonify({"error": "File expired or not found"}), 404

    return send_file(filepath, as_attachment=True, download_name=job.get("filename", "download"))


if __name__ == "__main__":
    print("\n🎬 YouTube to MP3/MP4 Converter")
    print("=" * 40)
    print("Open in your browser:")
    print("  PC/Phone:  http://localhost:5000")
    print("  Or from another device on same WiFi:")
    print(f"  http://{_get_local_ip()}:5000")
    print("=" * 40)
    print("Press Ctrl+C to stop.\n")
    app.run(host="0.0.0.0", port=5000, debug=True)


def _get_local_ip():
    """Get local network IP for phone access."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"
