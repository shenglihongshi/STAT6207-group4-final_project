@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================
echo  本地 LLM 批量抽取  JD + CV 共 150 份
echo  模型：qwen/qwen3.5-9b  (LM Studio, 端口 1235)
echo  已完成的会自动跳过，可随时关掉再重开续跑
echo ================================================
echo.

"C:\Users\admin\.workbuddy\binaries\python\versions\3.13.12\python.exe" extract.py --all

echo.
echo ================================================
echo  抽取结束。上面的最后一行是统计结果。
echo  明细日志：..\match_work\extract_log.txt
echo  结构化结果：..\match_work\extracted\
echo ================================================
echo.
echo 按任意键关闭窗口。
pause >nul
