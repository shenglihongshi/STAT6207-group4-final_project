@echo off
setlocal
title AI Candidate Matcher
echo ==================================================
echo   Second Talent - AI Candidate Matcher
echo ==================================================
echo.
echo   Starting the local server.
echo   The browser will open automatically in a few seconds.
echo.
echo   KEEP THIS WINDOW OPEN. Closing it stops the server.
echo ==================================================
echo.
netstat -ano ^| findstr /R /C:":5000 .*LISTENING" ^>nul
if not errorlevel 1 (
  echo   [WARNING] Port 5000 is already in use.
  echo.
  echo   Another copy of this program is probably still running.
  echo   Close the other black window, or end python.exe in
  echo   Task Manager, then double-click this file again.
  echo.
  pause
  exit /b 1
)
call "%~dp0matcher\start_web.bat"
