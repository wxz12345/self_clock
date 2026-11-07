# -*- coding: utf-8 -*-
"""放弃专注时的分心原因弹窗（温和记录型的核心交互：放弃必须"认账"）。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QDialog, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout)

REASONS = [
    "刷手机了", "社交/聊天", "被人打断",
    "任务太难/卡住", "累了/发呆", "想吃东西/喝水",
]


class DistractionDialog(QDialog):
    """确定返回 reason / note；取消表示"继续专注"。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("记录这次分心")
        self.setMinimumWidth(460)
        self.reason: str = ""
        self.note: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title = QLabel("这次专注被中断了")
        title.setObjectName("h2")
        subtitle = QLabel("没关系，选一下原因——让数据帮你找到规律。")
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setSpacing(10)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for i, reason in enumerate(REASONS):
            btn = QPushButton(reason)
            btn.setCheckable(True)
            btn.setMinimumHeight(44)
            btn.setCursor(Qt.PointingHandCursor)
            self._group.addButton(btn, i)
            grid.addWidget(btn, i // 2, i % 2)
        layout.addLayout(grid)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("补充说明（可选）")
        layout.addWidget(self.note_edit)

        buttons = QHBoxLayout()
        cancel = QPushButton("点错了，继续专注")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton("确认放弃")
        confirm.setObjectName("primary")
        confirm.clicked.connect(self._confirm)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)

    def _confirm(self) -> None:
        checked = self._group.checkedId()
        if checked < 0:
            self.reason = "其他"
        else:
            self.reason = REASONS[checked]
        self.note = self.note_edit.text().strip()
        self.accept()
