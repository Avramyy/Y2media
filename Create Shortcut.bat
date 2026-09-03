@echo off
echo Creating desktop shortcut for YouTube Downloader...

set "SCRIPT_DIR=%~dp0"
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\YouTube Downloader.lnk"

:: Create shortcut using PowerShell
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%SHORTCUT_PATH%'); $sc.TargetPath = '%SCRIPT_DIR%Start App (Silent).vbs'; $sc.WorkingDirectory = '%SCRIPT_DIR%'; $sc.IconLocation = '%SCRIPT_DIR%static\icon.svg,0'; $sc.Description = 'YouTube to MP3/MP4 Downloader'; $sc.WindowStyle = 7; $sc.Save()"

echo.
if exist "%SHORTCUT_PATH%" (
    echo  Shortcut created on Desktop!
    echo  You can now double-click "YouTube Downloader" on your Desktop.
) else (
    echo  Could not create shortcut.
)
echo.
pause
