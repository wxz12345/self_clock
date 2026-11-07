# -*- coding: utf-8 -*-
"""开机自启：写/删注册表 HKCU Run 项。仅 Windows 可用。"""
import os
import sys

try:
    import winreg
except ImportError:  # 非 Windows（开发容错）
    winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "SelfClock"


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _command() -> str:
    if getattr(sys, "frozen", False):  # 打包 exe
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{os.path.join(_project_root(), "main.py")}"'


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(on: bool) -> None:
    if winreg is None:
        return
    if on:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except OSError:
            pass
