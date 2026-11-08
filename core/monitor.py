# -*- coding: utf-8 -*-
"""黑名单前台窗口监控线程。

设计要点（调研自 Focuser 的进程匹配 + ActivityWatch 主动窗口监控思路）：
- 只检测【前台窗口】所属进程——Steam 挂在后台不算分心，切过去用它才算；
- 匹配方式：进程名的小写包含匹配（关键词 "steam" 命中 "steam.exe"）；
- 温和模式：命中后只发信号（由主线程通知+落库），绝不杀进程；
- 同一关键词 5 分钟内不重复上报，避免刷屏；
- 每次采样同时把采样时刻（time.monotonic）发给主线程，用于按真实
  墙钟时间累计应用使用时长——主线程被弹窗阻塞、信号排队时也不会算错。
"""
import ctypes
import logging
import time
from ctypes import wintypes

import psutil
from PySide6.QtCore import QThread, Signal

CHECK_INTERVAL_SEC = 5
DEDUP_WINDOW_SEC = 300

# 显式声明 Win32 函数签名：64 位进程里 HWND 是指针宽度，
# 用 ctypes 默认的 c_int 返回值会截断句柄，导致偶发取不到前台窗口。
try:
    _USER32 = ctypes.WinDLL("user32", use_last_error=True)
    _USER32.GetForegroundWindow.argtypes = []
    _USER32.GetForegroundWindow.restype = wintypes.HWND
    _USER32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _USER32.GetWindowThreadProcessId.restype = wintypes.DWORD
except AttributeError:  # pragma: no cover - 非 Windows 平台
    _USER32 = None


def get_foreground_process_name() -> str | None:
    """返回当前前台窗口所属进程名（如 notepad.exe），失败返回 None。"""
    if _USER32 is None:
        return None
    try:
        hwnd = _USER32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        _USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        return psutil.Process(pid.value).name()
    except (psutil.Error, OSError, ValueError):
        # 进程已退出 / 无权限（如提权窗口）属正常情况，静默跳过
        return None
    except Exception:
        logging.getLogger(__name__).exception("读取前台进程失败")
        return None


class FrontendMonitor(QThread):
    distraction_detected = Signal(str)          # 命中的进程名
    foreground_sample = Signal(str, float)      # (前台进程名, 采样时刻 monotonic)

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
        # 时间戳由本线程生成：主线程即使因弹窗/事件循环阻塞而延迟处理信号，
        # 相邻采样点之间的时长依然是真实的墙钟间隔。
        self.foreground_sample.emit(name, time.monotonic())
        low = name.lower()
        now = time.time()
        for keyword in self._blacklist:
            kw = keyword.lower()
            if kw in low and now - self._last_hit.get(kw, 0.0) >= DEDUP_WINDOW_SEC:
                self._last_hit[kw] = now
                self.distraction_detected.emit(name)
                break
