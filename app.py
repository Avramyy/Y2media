#!/usr/bin/env python3
"""
YouTube to MP3/MP4 Converter
Cross-platform web app that runs on PC and phone via browser.
"""

import os
import re
import uuid
import time
import socket
import threading
import yt_dlp
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

jobs = {}


def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def cleanup_old_files():
    now = time.time()
    for fname in os.listdir(DOWNLOAD_DIR):
        fpath = os.path.join(DOWNLOAD_DIR, fname)
        if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > 1800:
            try:
                os.remove(fpath)
            except OSError:
                pass


def progress_hook(d, job_id):
    """Track multi-stream download bytes. Capped at 90% — FFmpeg gets 90-100%."""
    if job_id not in jobs:
        return
    job = jobs[job_id]

    if d["status"] == "downloading":
        filename = d.get("filename", "unknown")
        if "_streams" not in job:
            job["_streams"] = {}

        downloaded = d.get("downloaded_bytes") or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0

        if filename not in job["_streams"]:
            job["_streams"][filename] = {"total": total, "downloaded": 0}
        job["_streams"][filename]["downloaded"] = downloaded
        if total > 0:
            job["_streams"][filename]["total"] = total

        total_all = sum(s["total"] for s in job["_streams"].values())
        downloaded_all = sum(s["downloaded"] for s in job["_streams"].values())

        if total_all > 0:
            new_pct = min(int((downloaded_all / total_all) * 90), 90)
        else:
            if "_dl_start" not in job:
                job["_dl_start"] = time.time()
            new_pct = min(int((time.time() - job["_dl_start"]) * 1), 15)

        if new_pct > job.get("progress", 0):
            job["progress"] = new_pct

    elif d["status"] == "finished":
        job["status"] = "processing"


def animate_processing(job_id, crawl_duration):
    """Wait for processing to start, then smoothly crawl from 91 to 100%.
    
    Updates every 1 second using time-based interpolation.
    """
    # Wait for download to finish and processing to start
    deadline = time.time() + 600
    while time.time() < deadline:
        status = jobs.get(job_id, {}).get("status")
        if status != "downloading":
            break
        time.sleep(0.5)

    if job_id not in jobs or jobs[job_id].get("status") != "processing":
        return

    # Smooth crawl: 91% -> 100% over crawl_duration seconds
    start_time = time.time()
    start_pct = 91
    end_pct = 100
    total_range = end_pct - start_pct  # 9 points

    while jobs.get(job_id, {}).get("status") == "processing":
        elapsed = time.time() - start_time
        ratio = min(elapsed / crawl_duration, 1.0)
        pct = int(start_pct + total_range * ratio)
        pct = min(pct, 99)
        jobs[job_id]["progress"] = pct
        time.sleep(1)

    # Processing done — jump to 100%
    if job_id in jobs:
        jobs[job_id]["progress"] = 100


def do_download(url, fmt, quality, job_id):
    try:
        unique = uuid.uuid4().hex[:10]
        output_template = os.path.join(DOWNLOAD_DIR, f"{unique}_%(title)s.%(ext)s")

        if fmt == "mp3":
            audio_q = {"128": "128", "192": "192", "256": "256", "320": "320"}.get(quality, "192")
            opts = {
                "format": "bestaudio/best",
                "outtmpl": output_template,
                "progress_hooks": [lambda d: progress_hook(d, job_id)],
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": audio_q}],
                "quiet": True, "no_warnings": True, "noplaylist": True,
            }
            crawl_duration = 300.0
        else:
            h = {"360": "360", "480": "480", "720": "720", "1080": "1080", "best": "best"}.get(quality, "720")
            fmt_str = "bestvideo+bestaudio/best" if h == "best" else (
                f"bestvideo[height<={h}]+bestaudio/bestvideo[height<={h}]+bestaudio[ext=m4a]/best[height<={h}]/best"
            )
            opts = {
                "format": fmt_str, "merge_output_format": "mp4", "outtmpl": output_template,
                "progress_hooks": [lambda d: progress_hook(d, job_id)],
                "quiet": True, "no_warnings": True, "noplaylist": True,
            }
            crawl_duration = 60.0

        # Start processing animator — waits for "processing" then crawls
        t = threading.Thread(target=animate_processing, args=(job_id, crawl_duration), daemon=True)
        t.start()

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        if info:
            ext = "mp3" if fmt == "mp3" else "mp4"
            safe = "".join(c if c.isalnum() or c in " _-" else "" for c in info.get("title", "video"))[:60]
            final_name = f"{safe}.{ext}"
            final_path = os.path.join(DOWNLOAD_DIR, final_name)
            actual = None
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(unique):
                    actual = os.path.join(DOWNLOAD_DIR, f)
                    break
            if actual and os.path.exists(actual):
                if actual != final_path and os.path.exists(final_path):
                    os.remove(final_path)
                os.rename(actual, final_path)
                jobs[job_id].update(filepath=final_path, filename=final_name, status="done")
            else:
                jobs[job_id].update(status="error", error="File not found after download")
        else:
            jobs[job_id].update(status="error", error="Could not extract video info")

    except yt_dlp.utils.DownloadError as e:
        msg = re.sub(r'\x1b\[[0-9;]*m', '', str(e))
        if "not available on this app" in msg.lower():
            msg = "This video is restricted by YouTube and cannot be downloaded."
        elif "Sign in" in msg or "login" in msg.lower():
            msg = "This video may be private or age-restricted and cannot be downloaded."
        elif "Private video" in msg:
            msg = "This video is private and cannot be downloaded."
        elif "Video unavailable" in msg:
            msg = "This video is unavailable."
        elif "Premiere" in msg:
            msg = "This video is a premiere and not yet available."
        elif "is live" in msg.lower():
            msg = "Live streams cannot be downloaded."
        else:
            msg = re.sub(r'\[youtube\]\s*\w+:\s*', '', msg)[:150]
        jobs[job_id].update(status="error", error=msg)
    except Exception:
        jobs[job_id].update(status="error", error="Something went wrong. Try another video.")


@app.route("/")
def index():
    cleanup_old_files()
    return render_template("index.html")


@app.route("/api/info", methods=["POST"])
def video_info():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    if not any(d in url for d in ["youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com"]):
        return jsonify({"error": "Not a YouTube URL"}), 400
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            return jsonify({"error": "Could not fetch video info"}), 404
        thumb = info.get("thumbnail")
        if not thumb and info.get("thumbnails"):
            thumbs = sorted(info["thumbnails"], key=lambda t: t.get("width", 0) * t.get("height", 0), reverse=True)
            thumb = thumbs[0].get("url") if thumbs else None
        dur = info.get("duration", 0)
        ds = ""
        if dur:
            m, s = divmod(int(dur), 60)
            h, m = divmod(m, 60)
            ds = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        return jsonify({"title": info.get("title", ""), "thumbnail": thumb, "duration": ds, "channel": info.get("channel", info.get("uploader", ""))})
    except yt_dlp.utils.DownloadError:
        return jsonify({"error": "Video not found or unavailable"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.get_json()
    url = data.get("url", "").strip()
    fmt = data.get("format", "mp4")
    quality = data.get("quality", "720")
    if not url:
        return jsonify({"error": "Please enter a YouTube URL"}), 400
    if not any(d in url for d in ["youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com"]):
        return jsonify({"error": "This is not a YouTube link"}), 400
    if fmt not in ("mp3", "mp4"):
        return jsonify({"error": "Format must be mp3 or mp4"}), 400
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {"status": "downloading", "progress": 0, "filepath": None, "filename": None, "error": None, "created": time.time()}
    threading.Thread(target=do_download, args=(url, fmt, quality, job_id), daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    resp = {"status": job["status"], "progress": job["progress"]}
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
    if not os.path.exists(job["filepath"]):
        return jsonify({"error": "File expired or not found"}), 404
    return send_file(job["filepath"], as_attachment=True, download_name=job.get("filename", "download"))


if __name__ == "__main__":
    print("\nYouTube to MP3/MP4 Converter")
    print("=" * 40)
    print("  PC/Phone:  http://localhost:5000")
    print(f"  Phone:     http://{_get_local_ip()}:5000")
    print("=" * 40)
    print("Press Ctrl+C to stop.\n")
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
