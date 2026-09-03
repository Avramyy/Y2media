#!/usr/bin/env python3
"""Start the server as a background process."""
import subprocess
import sys
import os

# Detach and run Flask
proc = subprocess.Popen(
    [sys.executable, "-c", "from app import app; app.run(host='127.0.0.1', port=5000, debug=False)"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    cwd=os.path.dirname(os.path.abspath(__file__)),
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
)
print(f"Server started with PID {proc.pid}")
print("Open http://127.0.0.1:5000 in your browser")
