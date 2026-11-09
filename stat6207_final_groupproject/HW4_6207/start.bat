@echo off
cd /d "%~dp0"
echo ============================================================
echo  HW4 6207 - quick start (uses cached keywords/metrics)
echo ============================================================
python run_pipeline.py %*
if errorlevel 1 (
  echo.
  echo Pipeline failed. See the error above.
  pause
  exit /b 1
)
echo.
pause
