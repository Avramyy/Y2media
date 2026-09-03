@echo off
title YouTube Downloader
echo ============================================
echo    YouTube to MP3/MP4 Downloader
echo ============================================
echo.
echo Starting server...

:: Start Flask in background
start "" /B pythonw -c "from app import app; app.run(host='0.0.0.0', port=5000, debug=False)"

:: Wait for server to start using ping (works on all Windows)
ping -n 3 127.0.0.1 >nul

:: Open browser
start http://localhost:5000

:: Show instructions
echo.
echo  Server is running!
echo.
echo  PC:     http://localhost:5000
echo.
echo  Phone:  Connect to the same WiFi,
echo          then open the address below.
echo.

:: Show local IP for phone
python -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); ip=s.getsockname()[0]; s.close(); print('  Your network IP:', ip); print('  Phone URL: http://'+ip+':5000')"

echo.
echo ============================================
echo  Close this window to STOP the server.
echo ============================================
echo.
pause
