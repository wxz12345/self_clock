# -*- coding: utf-8 -*-
"""点 X 关闭主窗口时的选择弹窗：最小化到托盘 / 退出，可记住选择。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout)


class CloseDialog(QDialog):
    """确定后：action 属性为 'tray' 或 'exit'；remember 表示记住选择。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关闭自律番茄钟")
        self.setMinimumWidth(400)
        self.action = "tray"
        self.remember = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(14)

        title = QLabel("关闭主窗口后要做什么？")
        title.setObjectName("h2")
        hint = QLabel("专注计时不受影响——最小化到托盘后会继续进行。")
        hint.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(hint)

        self.remember_check = QCheckBox("记住我的选择，下次不再询问")
        self.remember_check.setChecked(True)
        layout.addWidget(self.remember_check)
        layout.addSpacing(4)

        buttons = QHBoxLayout()
        tray_btn = QPushButton("最小化到托盘")
        tray_btn.setObjectName("primary")
        tray_btn.setFixedHeight(40)
        tray_btn.clicked.connect(lambda: self._pick("tray"))
        exit_btn = QPushButton("退出程序")
        exit_btn.setFixedHeight(40)
        exit_btn.clicked.connect(lambda: self._pick("exit"))
        buttons.addWidget(tray_btn)
        buttons.addWidget(exit_btn)
        layout.addLayout(buttons)

    def _pick(self, action: str) -> None:
        self.action = action
        self.remember = self.remember_check.isChecked()
        self.accept()
