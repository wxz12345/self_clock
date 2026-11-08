# -*- coding: utf-8 -*-
"""迷你窗三窗口结构：
- MiniOverlay：视觉窗（卡片+圆环+时间），整窗点击穿透（WS_EX_TRANSPARENT），
  可以直接点击它下面的窗口
- MiniGrip   ：左上角 26x26 的拖拽把手（可交互），拖动时移动整体
- MiniControls：按钮行（暂停/放弃/跳过/返回），贴在视觉窗下方

拆三个窗口的原因：Windows 的 WM_NCHITTEST/HTTRANSPARENT 只在同线程窗口间有效，
跨进程的局部穿透做不到；WS_EX_TRANSPARENT 是整窗生效。因此把"可交互部分"
（把手、按钮）各自做成独立窗口，视觉窗保持全穿透。
"""
import ctypes
import sys

from PySide6.QtCore import (QPointF, QTimer, QPoint, QRectF, Qt, Signal)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QHBoxLayout, QMenu, QPushButton,
                               QVBoxLayout, QWidget)

from . import theme

SIZE_W = 230
VISUAL_H = 168          # 视觉窗高度（卡片+圆环）
CONTROLS_H = 44         # 控制窗高度（按钮行）
GRIP_SIZE = 30          # 拖拽把手窗口尺寸
RING_D = SIZE_W - 92
RING_TOP = 18           # 圆环顶部（视觉窗内）

IS_WINDOWS = sys.platform == "win32"

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20
WS_EX_NOACTIVATE = 0x08000000


def _set_click_through(hwnd: int) -> None:
    """给原生窗口加 WS_EX_TRANSPARENT：整窗鼠标事件穿透到下层窗口。"""
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(
        hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED)


class MiniOverlay(QWidget):
    """视觉窗：圆环 + 时间，整窗点击穿透。"""

    moved = Signal(QPoint)   # 位置变化（含系统移动），供其他窗口跟随

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFixedSize(SIZE_W, VISUAL_H)
        self._time_text = "--:--"
        self._progress = 0.0
        self._color = theme.ACCENT
        self._opacity = 1.0

    def set_display(self, time_text: str, progress: float,
                    phase_key: str) -> None:
        self._time_text = time_text
        self._progress = max(0.0, min(1.0, progress))
        self._color = theme.PHASE_COLORS.get(phase_key, theme.ACCENT)
        self.update()

    def set_opacity(self, percent: int) -> None:
        self._opacity = max(0.15, min(1.0, percent / 100.0))
        self.update()

    def enable_click_through(self) -> None:
        if IS_WINDOWS and self.isVisible():
            _set_click_through(int(self.winId()))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if IS_WINDOWS:
            QTimer.singleShot(0, self.enable_click_through)

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self.moved.emit(self.pos())

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        op = self._opacity
        card = QColor(theme.OVERLAY[0], theme.OVERLAY[1], theme.OVERLAY[2],
                      int(theme.OVERLAY[3] * op))
        p.setPen(Qt.NoPen)
        p.setBrush(card)
        p.drawRoundedRect(QRectF(4, 4, SIZE_W - 8, VISUAL_H - 8), 18, 18)

        ring_rect = QRectF((SIZE_W - RING_D) / 2, RING_TOP, RING_D, RING_D)
        track = QPen(self._fade(QColor(theme.CARD_2)), 6)
        track.setCapStyle(Qt.RoundCap)
        p.setPen(track)
        p.drawArc(ring_rect, 0, 360 * 16)
        if self._progress > 0:
            prog = self._fade(QColor(self._color))
            pen = QPen(prog, 6)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(ring_rect, 90 * 16, int(-360 * self._progress * 16))

        p.setPen(self._fade(QColor(theme.TEXT)))
        font = QFont()
        font.setPixelSize(24)
        font.setBold(True)
        p.setFont(font)
        p.drawText(ring_rect, Qt.AlignHCenter | Qt.AlignVCenter,
                   self._time_text)
        p.end()

    def _fade(self, color: QColor) -> QColor:
        c = QColor(color)
        c.setAlpha(max(0, min(255, int(c.alpha() * self._opacity))))
        return c


class MiniGrip(QWidget):
    """左上角拖拽把手：可交互的小窗口，拖动时移动整个迷你窗。"""

    drag_moved = Signal(QPoint)   # 新的左上角坐标（把手的左上角）
    drag_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(GRIP_SIZE, GRIP_SIZE)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("拖动移动迷你窗")
        self._drag_offset: QPoint | None = None
        self._opacity = 1.0

    def set_opacity(self, percent: int) -> None:
        self._opacity = max(0.15, min(1.0, percent / 100.0))
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self.drag_moved.emit(self.pos())

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            self.setCursor(Qt.OpenHandCursor)
            self.drag_finished.emit()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        dot = QColor(theme.TEXT_DIM)
        dot.setAlpha(int(150 * self._opacity))
        p.setBrush(dot)
        cx, cy = GRIP_SIZE / 2, GRIP_SIZE / 2
        for dy in (-7, 0, 7):
            p.drawEllipse(QPointF(cx, cy + dy), 2.6, 2.6)
        p.end()


class MiniControls(QWidget):
    """控制窗：状态标签 + 按钮行（暂停/放弃/跳过/返回）。"""

    primary_requested = Signal()
    abandon_requested = Signal()
    skip_requested = Signal()
    expand_requested = Signal()
    opacity_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(SIZE_W, CONTROLS_H)
        self._opacity = 1.0
        self._label = "待机"

        self.setStyleSheet("QPushButton { padding: 3px 8px; font-size: 12px; }")
        self.btn_primary = QPushButton("开始专注")
        self.btn_primary.setObjectName("primary")
        self.btn_primary.setFixedHeight(30)
        self.btn_primary.setMinimumWidth(88)
        self.btn_primary.clicked.connect(self.primary_requested.emit)
        self.btn_abandon = QPushButton("放弃")
        self.btn_abandon.setObjectName("danger")
        self.btn_abandon.setFixedHeight(30)
        self.btn_abandon.clicked.connect(self.abandon_requested.emit)
        self.btn_skip = QPushButton("跳过")
        self.btn_skip.setFixedHeight(30)
        self.btn_skip.clicked.connect(self.skip_requested.emit)
        self.btn_expand = QPushButton("返回")
        self.btn_expand.setToolTip("返回主窗口")
        self.btn_expand.setFixedHeight(30)
        self.btn_expand.setFixedWidth(52)
        self.btn_expand.clicked.connect(self.expand_requested.emit)

        row = QHBoxLayout()
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(5)
        row.addWidget(self.btn_primary, stretch=1)
        row.addWidget(self.btn_abandon)
        row.addWidget(self.btn_skip)
        row.addWidget(self.btn_expand)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.addLayout(row)

    def set_actions(self, primary_text: str, show_primary: bool,
                    show_abandon: bool, show_skip: bool) -> None:
        self.btn_primary.setText(primary_text)
        self.btn_primary.setVisible(show_primary)
        self.btn_abandon.setVisible(show_abandon)
        self.btn_skip.setVisible(show_skip)

    def set_state_label(self, label: str) -> None:
        """保留接口（状态已由圆环颜色表达，按钮行不再绘制文字）。"""
        self._label = label

    def set_opacity(self, percent: int) -> None:
        self._opacity = max(0.15, min(1.0, percent / 100.0))
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        op = self._opacity
        card = QColor(theme.OVERLAY[0], theme.OVERLAY[1], theme.OVERLAY[2],
                      int(theme.OVERLAY[3] * op))
        p.setPen(Qt.NoPen)
        p.setBrush(card)
        p.drawRoundedRect(QRectF(4, 4, SIZE_W - 8, CONTROLS_H - 8), 14, 14)
        p.end()
