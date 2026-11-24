@echo off
setlocal
title AI Candidate Matcher
cd /d "%~dp0"
echo ================================================
echo   AI Candidate Matcher - Local Server
echo ================================================
echo.
echo   Browser will open at http://127.0.0.1:5000
echo.
echo   [1] Click an example job    - no model needed, instant
echo   [2] Upload or paste new JD  - needs LM Studio Start Server
echo.
echo   KEEP THIS WINDOW OPEN. Closing it stops the server.
echo ================================================
echo.
"C:\Users\admin\.workbuddy\binaries\python\versions\3.13.12\python.exe" app.py
echo.
echo Server stopped. Press any key to close.
pause >nul
