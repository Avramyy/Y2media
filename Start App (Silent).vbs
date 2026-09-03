Set WshShell = CreateObject("WScript.Shell")
appPath = WshShell.CurrentDirectory

' Start server silently (no console window)
WshShell.Run "pythonw -c ""from app import app; app.run(host='0.0.0.0', port=5000, debug=False)""", 0, False

' Wait for server to start
WScript.Sleep 2500

' Open browser
WshShell.Run "http://localhost:5000"
