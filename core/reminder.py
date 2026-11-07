# -*- coding: utf-8 -*-
"""提醒事项调度器：主线程 QTimer 周期扫描到期提醒。

应用未运行期间错过的提醒（remind_ts 早已过期）会在启动后首次扫描时补发，
并通过 missed 标记让弹窗显示"已错过"。
"""
import time

from PySide6.QtCore import QObject, QTimer, Signal

POLL_INTERVAL_MS = 20000
# 超过这个宽限期的到期提醒视为"错过"（应用当时没在运行）
MISSED_GRACE_SEC = 60


class ReminderScheduler(QObject):
    due = Signal(dict)  # reminder 行字典（含 missed: bool）

    def __init__(self, store):
        super().__init__()
        self._store = store
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self.check)
        self._timer.start()
        self.check()  # 启动即补扫一次

    def check(self) -> None:
        now = time.time()
        for row in self._store.due_reminders(now):
            self._store.mark_reminder_reminded(row["id"])
            self.due.emit({**dict(row), "missed": now - row["remind_ts"] > MISSED_GRACE_SEC})
