# -*- coding: utf-8 -*-
"""游戏化小树：随累计金币长大（阶段），专注时随进度生长并轻轻摇摆。

全部由 QPainter 程序化绘制：树干 + 团状树冠 + 花盆，无任何素材依赖。
"""
import math

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import (QBrush, QColor, QLinearGradient, QPainter,
                           QPainterPath, QPen)
from PySide6.QtWidgets import QWidget

from . import theme

TRUNK = "#8a6a4f"
CANOPY = ["#3f9d5a", "#4fb96b", "#6fcf7c"]


class TreeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._stage = 0          # 0 种子 / 1 幼苗 / 2 小树 / 3 大树
        self._grow = 0.0         # 本次专注进度 0~1
        self._running = False
        self._t = 0.0
        self.setMinimumSize(200, 220)
        self._anim = QTimer(self)
        self._anim.setInterval(66)
        self._anim.timeout.connect(self._sway)

    def set_state(self, stage: int, grow: float, running: bool) -> None:
        self._stage = max(0, min(3, stage))
        self._grow = max(0.0, min(1.0, grow))
        self._running = running
        if running:
            self._anim.start()
        else:
            self._anim.stop()
            self._t = 0.0
        self.update()

    def _sway(self) -> None:
        self._t += 0.10
        self.update()

    # ---------- 绘制 ----------
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        base_y = h - 26.0
        cx = w / 2.0

        # 地面阴影
        p.setPen(Qt.NoPen)
        shadow = QColor(0, 0, 0, 60)
        p.setBrush(QBrush(shadow))
        p.drawEllipse(QPointF(cx, base_y + 6), w * 0.24, 7)

        # 花盆
        pot_top, pot_h = base_y, 22.0
        path = QPainterPath()
        path.moveTo(cx - w * 0.13, pot_top)
        path.lineTo(cx + w * 0.13, pot_top)
        path.lineTo(cx + w * 0.10, pot_top + pot_h)
        path.lineTo(cx - w * 0.10, pot_top + pot_h)
        path.closeSubpath()
        grad = QLinearGradient(cx - w * 0.13, pot_top, cx + w * 0.13, pot_top)
        grad.setColorAt(0, QColor("#b0703f"))
        grad.setColorAt(1, QColor("#8a5530"))
        p.setBrush(QBrush(grad))
        p.drawPath(path)

        sway = math.sin(self._t) * (4.0 if self._running else 1.2)
        # 生长系数：闲置时按阶段展示；专注时从当前阶段的 55% 长到 100%
        scale = (0.35, 0.6, 0.85, 1.15)[self._stage]
        grow_factor = (0.55 + 0.45 * self._grow) if self._running else 1.0
        size = min(w, h) * 0.42 * scale * grow_factor

        if self._stage == 0:
            self._draw_seed(p, cx, pot_top, size, sway)
        elif self._stage == 1:
            self._draw_sprout(p, cx, pot_top, size, sway)
        else:
            self._draw_tree(p, cx, pot_top, size, sway)
        p.end()

    def _draw_seed(self, p: QPainter, cx: float, base_y: float, size: float,
                   sway: float) -> None:
        # 土堆 + 种子
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#5a4634")))
        p.drawEllipse(QPointF(cx, base_y - 4), size * 0.16, size * 0.07)
        p.setBrush(QBrush(QColor("#c9a06a")))
        seed = QRectF(cx - size * 0.06 + sway * 0.2, base_y - size * 0.13,
                      size * 0.12, size * 0.16)
        p.drawEllipse(seed)
        p.setBrush(QBrush(QColor(theme.ACCENT)))
        p.drawEllipse(QPointF(cx + size * 0.05 + sway * 0.2,
                              base_y - size * 0.12), 2.2, 2.2)

    def _draw_sprout(self, p: QPainter, cx: float, base_y: float, size: float,
                     sway: float) -> None:
        pen = QPen(QColor(theme.ACCENT_DIM), max(2.0, size * 0.05))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        top = base_y - size * 0.55
        p.drawLine(QPointF(cx, base_y - 6), QPointF(cx + sway * 0.4, top))
        # 两片子叶
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(theme.ACCENT)))
        for sign in (-1, 1):
            lx = cx + sway * 0.4 + sign * size * 0.12
            ly = top + size * 0.05
            leaf = QPainterPath()
            leaf.moveTo(cx + sway * 0.4, top)
            leaf.cubicTo(QPointF(lx, ly - size * 0.10),
                         QPointF(lx + sign * size * 0.10, ly + size * 0.02),
                         QPointF(cx + sway * 0.4, top + size * 0.08))
            p.drawPath(leaf)

    def _draw_tree(self, p: QPainter, cx: float, base_y: float, size: float,
                   sway: float) -> None:
        # 树干（带一点弯曲）
        trunk_pen = QPen(QColor(TRUNK), max(4.0, size * 0.10))
        trunk_pen.setCapStyle(Qt.RoundCap)
        p.setPen(trunk_pen)
        mid_y = base_y - size * 0.45
        top_y = base_y - size * 0.95
        path = QPainterPath()
        path.moveTo(cx, base_y - 6)
        path.quadTo(QPointF(cx + sway * 0.5, mid_y), QPointF(cx + sway, top_y))
        p.drawPath(path)

        # 树冠：三团圆（大树更大更满）
        p.setPen(Qt.NoPen)
        apex = QPointF(cx + sway, top_y - size * 0.10)
        blobs = [
            (apex.x(), apex.y(), size * 0.30),
            (apex.x() - size * 0.26, apex.y() + size * 0.22, size * 0.24),
            (apex.x() + size * 0.26, apex.y() + size * 0.24, size * 0.25),
        ]
        for i, (bx, by, br) in enumerate(blobs):
            p.setBrush(QBrush(QColor(CANOPY[i % len(CANOPY)])))
            p.drawEllipse(QPointF(bx, by), br, br * 0.92)
        # 高光
        p.setBrush(QBrush(QColor(255, 255, 255, 28)))
        p.drawEllipse(QPointF(apex.x() - size * 0.08, apex.y() - size * 0.08),
                      size * 0.10, size * 0.08)
        # 大树结果子
        if self._stage == 3:
            p.setBrush(QBrush(QColor(theme.FOCUS_COLOR)))
            for dx, dy in ((-0.18, 0.30), (0.15, 0.38), (-0.02, 0.20)):
                p.drawEllipse(QPointF(apex.x() + size * dx,
                                      apex.y() + size * dy), size * 0.045,
                              size * 0.045)
