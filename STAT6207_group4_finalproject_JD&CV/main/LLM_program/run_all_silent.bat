@echo off
cd /d "%~dp0"
"C:\Users\admin\.workbuddy\binaries\python\versions\3.13.12\python.exe" extract.py --all > "..\match_work\extract_stdout.txt" 2>&1
