# -*- coding: utf-8 -*-
"""黑名单前台窗口监控线程。

设计要点（调研自 Focuser 的进程匹配 + ActivityWatch 主动窗口监控思路）：
- 只检测【前台窗口】所属进程——Steam 挂在后台不算分心，切过去用它才算；
- 匹配方式：进程名的小写包含匹配（关键词 "steam" 命中 "steam.exe"）；
- 温和模式：命中后只发信号（由主线程通知+落库），绝不杀进程；
- 同一关键词 5 分钟内不重复上报，避免刷屏。
"""
import ctypes
import time
from ctypes import wintypes

import psutil
from PySide6.QtCore import QThread, Signal

CHECK_INTERVAL_SEC = 15
DEDUP_WINDOW_SEC = 300


def get_foreground_process_name() -> str | None:
    """返回当前前台窗口所属进程名（如 notepad.exe），失败返回 None。"""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        return psutil.Process(pid.value).name()
    except Exception:
        return None


class FrontendMonitor(QThread):
    distraction_detected = Signal(str)  # 命中的进程名
    foreground_sample = Signal(str)     # 每次采样的当前前台进程（应用使用统计用）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._blacklist: list[str] = []
        self._scanning = False
        self._stop = False
        self._last_hit: dict[str, float] = {}

    def set_blacklist(self, keywords: list[str]) -> None:
        self._blacklist = [k.strip() for k in keywords if k and k.strip()]

    def set_scanning(self, on: bool) -> None:
        self._scanning = on
        if on:
            self._last_hit.clear()

    def stop(self) -> None:
        self._stop = True
        self.wait(3000)

    def run(self) -> None:
        while not self._stop:
            if self._scanning:
                # 只要专注会话进行中就采样前台窗口（应用使用统计），
                # 黑名单命中判断在 _check_once 内部（黑名单为空时仅采样不告警）
                self._check_once()
                for _ in range(CHECK_INTERVAL_SEC * 10):
                    if self._stop:
                        return
                    self.msleep(100)
            else:
                for _ in range(10):
                    if self._stop:
                        return
                    self.msleep(100)

    def _check_once(self) -> None:
        name = get_foreground_process_name()
        if not name:
            return
        self.foreground_sample.emit(name)
        low = name.lower()
        now = time.time()
        for keyword in self._blacklist:
            kw = keyword.lower()
            if kw in low and now - self._last_hit.get(kw, 0.0) >= DEDUP_WINDOW_SEC:
                self._last_hit[kw] = now
                self.distraction_detected.emit(name)
                break
