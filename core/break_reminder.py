# -*- coding: utf-8 -*-
"""规律性久坐提醒：按固定间隔发出 fired 信号。不依赖 UI。"""
from PySide6.QtCore import QObject, QTimer, Signal

MIN_INTERVAL_MIN = 5


class BreakReminder(QObject):
    fired = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        # 只连接一次：configure 会被设置保存反复调用，重复 connect 会导致
        # 每个间隔触发多次提醒
        self._timer.timeout.connect(self.fired)

    @property
    def active(self) -> bool:
        return self._timer.isActive()

    @property
    def interval_minutes(self) -> float:
        return self._timer.interval() / 60000.0

    def configure(self, enabled: bool, minutes: int) -> None:
        self._timer.stop()
        if enabled:
            self._timer.setInterval(max(MIN_INTERVAL_MIN, int(minutes)) * 60 * 1000)
            self._timer.start()
