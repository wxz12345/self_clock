# -*- coding: utf-8 -*-
"""顺计时（秒表）：从 0 往上计，手动停止；与番茄钟互斥使用。"""
import time

from PySide6.QtCore import QObject, QTimer, Signal


class Stopwatch(QObject):
    tick = Signal(float)          # 已计时秒数
    state_changed = Signal()      # 运行/暂停/停止 变化
    stopped = Signal(float)       # 手动停止，携带本次分钟数

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accumulated = 0.0   # 暂停前累计的秒数
        self._since = 0.0         # 本段开始的时刻
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._on_tick)

    @property
    def running(self) -> bool:
        return self._running

    def elapsed_seconds(self) -> float:
        if self._running:
            return self._accumulated + (time.time() - self._since)
        return self._accumulated

    def elapsed_minutes(self) -> float:
        return self.elapsed_seconds() / 60.0

    # ---------- 控制 ----------
    def start(self) -> None:
        if self._running:
            return
        self._accumulated = 0.0
        self._since = time.time()
        self._running = True
        self._timer.start()
        self.state_changed.emit()
        self.tick.emit(0.0)

    def pause(self) -> None:
        if not self._running:
            return
        self._accumulated = self.elapsed_seconds()
        self._running = False
        self._timer.stop()
        self.state_changed.emit()

    def resume(self) -> None:
        if self._running:
            return
        self._since = time.time()
        self._running = True
        self._timer.start()
        self.state_changed.emit()

    def stop(self) -> float:
        """停止并返回本次分钟数（调用方负责落库）。"""
        minutes = self.elapsed_minutes()
        self._timer.stop()
        self._running = False
        self._accumulated = 0.0
        self.state_changed.emit()
        return minutes

    # ---------- 内部 ----------
    def _on_tick(self) -> None:
        self.tick.emit(self.elapsed_seconds())
