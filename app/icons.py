# -*- coding: utf-8 -*-
"""运行时代码绘制的应用图标（含 assets/app.ico 的加载）。"""
import os

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QIcon, QPainter, QPainterPath,
                           QPen, QPixmap)

from . import theme

_cache: dict[tuple[int, str], QIcon] = {}

ICON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "app.ico")


def _paint_pixmap(size: int, ring_color: str) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    # 深色圆角底
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(theme.CARD))
    margin = size * 0.06
    p.drawRoundedRect(QRectF(margin, margin, size - 2 * margin, size - 2 * margin),
                      size * 0.22, size * 0.22)

    # 进度环：底环 + 约 3/4 的亮环
    ring_rect = QRectF(size * 0.20, size * 0.24, size * 0.60, size * 0.60)
    track = QPen(QColor(theme.CARD_2), size * 0.075)
    track.setCapStyle(Qt.RoundCap)
    p.setPen(track)
    p.drawArc(ring_rect, 0, 360 * 16)
    ring = QPen(QColor(ring_color), size * 0.075)
    ring.setCapStyle(Qt.RoundCap)
    p.setPen(ring)
    p.drawArc(ring_rect, 90 * 16, -270 * 16)

    # 环顶的小叶子
    leaf = QPainterPath()
    cx, cy = size * 0.66, size * 0.14
    leaf.moveTo(cx, cy)
    leaf.cubicTo(QPointF(cx + size * 0.10, cy - size * 0.10),
                 QPointF(cx + size * 0.20, cy + size * 0.02),
                 QPointF(cx, cy + size * 0.06))
    leaf.cubicTo(QPointF(cx - size * 0.08, cy + size * 0.02),
                 QPointF(cx - size * 0.06, cy - size * 0.04),
                 QPointF(cx, cy))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(theme.ACCENT)))
    p.drawPath(leaf)
    p.end()
    return pm


def app_icon(size: int = 64, ring_color: str = theme.ACCENT) -> QIcon:
    key = (size, ring_color)
    if key not in _cache:
        _cache[key] = QIcon(_paint_pixmap(size, ring_color))
    return _cache[key]


def load_app_icon() -> QIcon:
    """优先加载 assets/app.ico（含 16~256 多尺寸），失败则回退运行时绘制。"""
    if os.path.exists(ICON_PATH):
        icon = QIcon(ICON_PATH)
        if not icon.isNull():
            return icon
    return app_icon()
