@echo off
cd /d "%~dp0"
set "PY=python"
python -c "import sys" >nul 2>nul
if errorlevel 1 set "PY=py -3"
%PY% extract.py --all > "..\match_work\extract_stdout.txt" 2>&1
