# -*- coding: utf-8 -*-
"""提醒事项到点弹窗：置顶显示，支持 完成 / 稍后 5 分钟 / 关闭。

返回值：QDialog.Accepted 且 action 属性说明用户选择
（'done' / 'snooze' / 'closed'）。
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)

from . import theme


class ReminderPopup(QDialog):
    def __init__(self, reminder: dict, parent=None):
        super().__init__(parent)
        self.action = "closed"
        self.setWindowTitle("⏰ 提醒")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(10)

        missed = reminder.get("missed")
        head = "⏰ 你错过了一条提醒" if missed else "⏰ 时间到了"
        head_label = QLabel(head)
        head_label.setObjectName("muted")
        layout.addWidget(head_label)

        title = QLabel(reminder["title"])
        title.setObjectName("h1")
        title.setWordWrap(True)
        layout.addWidget(title)

        from datetime import datetime
        event_ts = reminder.get("event_ts")
        if event_ts:
            event_line = QLabel(
                "📅 " + datetime.fromtimestamp(event_ts).strftime("%m-%d %H:%M"))
            layout.addWidget(event_line)
        if reminder.get("location"):
            loc = QLabel("📍 " + reminder["location"])
            loc.setWordWrap(True)
            layout.addWidget(loc)
        if reminder.get("note"):
            note = QLabel("📝 " + reminder["note"])
            note.setObjectName("muted")
            note.setWordWrap(True)
            layout.addWidget(note)

        layout.addSpacing(6)
        buttons = QHBoxLayout()
        done = QPushButton("✓ 完成")
        done.setObjectName("primary")
        done.clicked.connect(lambda: self._finish("done"))
        snooze = QPushButton("稍后 5 分钟")
        snooze.clicked.connect(lambda: self._finish("snooze"))
        close = QPushButton("关闭")
        close.clicked.connect(lambda: self._finish("closed"))
        buttons.addWidget(done)
        buttons.addWidget(snooze)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _finish(self, action: str) -> None:
        self.action = action
        self.accept()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
