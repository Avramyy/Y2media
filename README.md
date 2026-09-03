# 🎬 YouTube Downloader — MP3 & MP4

A free, cross-platform YouTube to MP3 and MP4 converter with quality selection. Runs on **PC, Mac, Linux, Android, and iPhone** — just open your browser!

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-All-brightgreen)

---

## ✨ Features

- **MP3 (Audio)** — 128, 192, 256, 320 kbps
- **MP4 (Video)** — 360p, 480p, 720p, 1080p, Best Quality
- **Responsive UI** — works on desktop and mobile browsers
- **Progress bar** — real-time download progress
- **Auto-cleanup** — files deleted after 30 minutes
- **No ads, no tracking** — 100% free and open source
- **Works on any device** — PC, phone, tablet

---

## 🚀 Quick Start (Windows)

### Option A: One-Click Launch

1. Install [Python](https://python.org) and [FFmpeg](https://ffmpeg.org/download.html)
2. Run `pip install -r requirements.txt` once
3. **Double-click `Start App.bat`** — server starts and browser opens!
4. Or **double-click `Start App (Silent).vbs`** — runs invisibly, just opens browser
5. Run `Create Shortcut.bat` once to add a desktop shortcut

### Option B: Command Line

```bash
# Clone the repo
git clone https://github.com/yourusername/youtube-downloader.git
cd youtube-downloader

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

### Access from Phone

When you run the app, it shows a local network URL like:

```
http://192.168.1.100:5000
```

**Steps:**
1. Make sure your phone is on the **same WiFi** as your PC
2. Open your phone's browser (Chrome/Safari)
3. Type the URL shown in the console (e.g. `http://192.168.1.100:5000`)
4. Done! The app works just like on PC

**Tip:** On Android, you can add it to your home screen:
- Open the URL in Chrome
- Tap the 3-dot menu > "Add to Home screen"
- Now it looks like a native app!

On iPhone:
- Open the URL in Safari
- Tap the Share button > "Add to Home Screen"
- It will appear as an app icon on your home screen

---

## 📁 Project Structure

```
youtube-downloader/
├── app.py              # Main Flask application
├── start_server.py     # Background server starter
├── Start App.bat       # Double-click to launch (Windows)
├── Start App (Silent).vbs  # Silent launcher (no console)
├── Create Shortcut.bat # Creates desktop shortcut
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Frontend UI
├── static/
│   └── icon.svg        # App icon
├── downloads/          # Temp files (auto-created)
├── .gitignore
└── README.md
```

---

## 🛠️ Tech Stack

- **Backend:** Python, Flask
- **Download engine:** yt-dlp
- **Audio conversion:** FFmpeg (via yt-dlp postprocessors)
- **Frontend:** Vanilla HTML/CSS/JS (no framework needed)

---

## 📱 How It Works

1. Paste a YouTube URL
2. Choose format (MP3 audio or MP4 video)
3. Pick your quality
4. Click Download
5. Save the file

---

## ⚠️ Disclaimer

This tool is for **personal use only**. Downloading copyrighted content without permission is illegal. Use responsibly.

---

## 📄 License

MIT License — use it however you want.
