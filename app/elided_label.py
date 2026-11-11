# -*- coding: utf-8 -*-
"""超长自动省略的单行标签。

普通 QLabel 的最小宽度等于整段文字的宽度：行内放一个很长的任务名/标题时，
整行（乃至整个页面）会被撑宽，右侧的按钮被挤出可视区域。
ElidedLabel 的最小宽度为 0，宽度不够时在末尾显示“…”，悬停可看全文。
"""
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full = ""
        # Ignored：布局不按文字全长给它留位置，剩余空间多少就显示多少
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def full_text(self) -> str:
        return self._full

    def setText(self, text: str) -> None:
        self._full = text
        self._apply()

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply()

    def changeEvent(self, event) -> None:   # 字体变化（如删除线）后重算
        super().changeEvent(event)
        if event.type() == event.Type.FontChange:
            self._apply()

    def _apply(self) -> None:
        width = max(0, self.contentsRect().width())
        shown = (self.fontMetrics().elidedText(self._full, Qt.ElideRight, width)
                 if width > 0 else self._full)
        if shown != self.text():
            super().setText(shown)
        # 只有被截断时才需要悬停提示
        self.setToolTip(self._full if shown != self._full else "")
