# -*- coding: utf-8 -*-
"""系统托盘：常驻图标、倒计时 tooltip、通知、快捷菜单。"""
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import icons


class TrayController(QSystemTrayIcon):
    def __init__(self, icon: QIcon | None = None, parent=None):
        super().__init__(icon or icons.load_app_icon(), parent)
        self.setToolTip("自律番茄钟")

        self.menu = QMenu()
        self.act_show = QAction("显示主窗口", self)
        self.act_toggle = QAction("开始专注", self)
        self.act_mini = QAction("显示迷你窗", self)
        self.act_theme = QAction("切换为浅色主题", self)
        self.act_quit = QAction("退出", self)
        self.menu.addAction(self.act_show)
        self.menu.addAction(self.act_toggle)
        self.menu.addAction(self.act_mini)
        self.menu.addAction(self.act_theme)
        self.menu.addSeparator()
        self.menu.addAction(self.act_quit)
        self.setContextMenu(self.menu)

        self.activated.connect(self._on_activated)
        self.show()

    def _on_activated(self, reason) -> None:
        # 双击/单击图标 → 显示主窗口
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger,
                      QSystemTrayIcon.MiddleClick):
            if self.parent() is not None:
                self.parent().showNormal()

    def set_theme_label(self, current_theme: str) -> None:
        """菜单项文字写“点击后会变成什么”：当前深色 → 切换为浅色，反之亦然。"""
        self.act_theme.setText(
            "切换为浅色主题" if current_theme == "dark" else "切换为深色主题")

    def notify(self, title: str, body: str, msecs: int = 5000) -> None:
        if self.isVisible():
            self.showMessage(title, body, QSystemTrayIcon.Information, msecs)

    def update_timer_tooltip(self, text: str) -> None:
        self.setToolTip(text)
