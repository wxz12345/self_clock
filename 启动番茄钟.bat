@echo off
rem 源码开发用启动脚本；普通用户请直接下载 Release 里的 SelfClock.exe
cd /d "%~dp0"
call conda activate self_clock
if errorlevel 1 (
    echo 未找到 conda 环境 self_clock，请先执行：
    echo   conda create -y -n self_clock python=3.11
    echo   conda run -n self_clock pip install -r requirements.txt
    pause
    exit /b 1
)
start "" pythonw main.py
