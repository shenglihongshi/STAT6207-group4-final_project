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

rem ---- locate Python 3 without hard-coding any interpreter path ----
set "PY="
python -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >nul 2>nul
if not errorlevel 1 set "PY=python"
if not defined PY (
    py -3 -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
    echo   [ERROR] Python 3 was not found on this computer.
    echo.
    echo   Install Python 3.10 or newer from https://www.python.org/downloads/
    echo   and tick "Add python.exe to PATH" during setup.
    echo   Then run this file again.
    echo.
    pause
    exit /b 1
)
echo   Interpreter : %PY%

rem ---- the server cannot start without these ----
%PY% -c "import flask, numpy" >nul 2>nul
if errorlevel 1 (
    echo.
    echo   [ERROR] Required packages are missing for this Python.
    echo   Run this once, then start again:
    echo.
    echo       %PY% -m pip install -r "%~dp0..\..\requirements.txt"
    echo.
    pause
    exit /b 1
)

echo.
%PY% app.py
echo.
echo Server stopped. Press any key to close.
pause >nul
