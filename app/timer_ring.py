# -*- coding: utf-8 -*-
"""番茄钟进度环：圆环进度 + 居中剩余时间。"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import theme


class TimerRing(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._time_text = "--:--"
        self._color = theme.FOCUS_COLOR
        self.setMinimumSize(300, 300)

    def set_display(self, time_text: str, progress: float, phase_key: str) -> None:
        self._time_text = time_text
        self._progress = max(0.0, min(1.0, progress))
        self._color = theme.PHASE_COLORS.get(phase_key, theme.ACCENT)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height())
        cx = (self.width() - side) / 2
        cy = (self.height() - side) / 2
        ring_rect = QRectF(cx + 14, cy + 14, side - 28, side - 28)
        pen_w = max(8.0, side * 0.045)

        # 底环
        track = QPen(QColor(theme.CARD_2), pen_w)
        track.setCapStyle(Qt.RoundCap)
        p.setPen(track)
        p.drawArc(ring_rect, 0, 360 * 16)

        # 进度弧（从 12 点顺时针）：先画一层宽而淡的辉光，再画主线
        if self._progress > 0:
            glow_color = QColor(self._color)  # 兼容十六进制字符串与 QColor
            glow_color.setAlpha(42)
            glow = QPen(glow_color, pen_w * 2.0)
            glow.setCapStyle(Qt.RoundCap)
            p.setPen(glow)
            p.drawArc(ring_rect, 90 * 16, int(-360 * self._progress * 16))
            pen = QPen(QColor(self._color), pen_w)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(ring_rect, 90 * 16, int(-360 * self._progress * 16))

        # 居中剩余时间
        p.setPen(QColor(theme.TEXT))
        font = QFont()
        font.setPixelSize(int(side * 0.21))
        font.setBold(True)
        p.setFont(font)
        text_rect = QRectF(0, cy + side * 0.28, self.width(), side * 0.3)
        p.drawText(text_rect, Qt.AlignHCenter | Qt.AlignVCenter, self._time_text)
        p.end()
