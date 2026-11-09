@echo off
cd /d "%~dp0"
set PATH=%PATH%;%USERPROFILE%\.lmstudio\bin

echo ============================================================
echo  HW4 6207 - full run (raw PDFs -^> LLM -^> AE -^> report)
echo  This can take 20-40 minutes because 120 documents are sent
echo  to the local Qwen model.
echo ============================================================

echo [1/3] starting LM Studio server...
lms server start

echo [2/3] loading models (first load may take 1-2 minutes)...
lms load qwen2.5-coder-14b-instruct --gpu max --context-length 8192 --identifier qwen2.5-coder-14b-instruct
lms load text-embedding-nomic-embed-text-v1.5 --gpu max --identifier nomic-embed

echo [3/3] running pipeline...
python run_pipeline.py --full
if errorlevel 1 (
  echo.
  echo Pipeline failed. See the error above.
  pause
  exit /b 1
)
echo.
pause
