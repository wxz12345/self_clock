@echo off
cd /d "%~dp0"
if exist "D:\pipcache\envs\self_clock\pythonw.exe" (
    start "" "D:\pipcache\envs\self_clock\pythonw.exe" main.py
) else (
    call conda activate self_clock
    start "" pythonw main.py
)
