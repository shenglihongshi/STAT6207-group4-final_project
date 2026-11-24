@echo off
cd /d "%~dp0"
set PATH=%PATH%;%USERPROFILE%\.lmstudio\bin

echo ============================================================
echo  HW4 6207 - GENERAL MODE
echo  Put CVs in data\input\cvs and JDs in data\input\jds
echo  Optional: data\input\ground_truth.csv
echo ============================================================

echo [1/3] starting LM Studio...
lms server start

echo [2/3] loading models...
lms load qwen2.5-coder-14b-instruct --gpu max --context-length 8192 --identifier qwen2.5-coder-14b-instruct
lms load text-embedding-nomic-embed-text-v1.5 --gpu max --identifier nomic-embed

echo [3/3] running general matching pipeline...
python run_general.py %*
if errorlevel 1 (
  echo.
  echo Pipeline failed. See the error above.
  pause
  exit /b 1
)
echo.
pause
