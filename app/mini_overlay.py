# -*- coding: utf-8 -*-
"""迷你窗双窗口结构：
- MiniOverlay：视觉窗（卡片+圆环+时间+拖拽把手）
  圆环区域点击穿透（WM_NCHITTEST → HTTRANSPARENT），左上角把手可拖动整体
- MiniControls：按钮行（暂停/放弃/跳过/返回），贴在视觉窗下方

拖动把手时两个窗口一起动；透明度只影响绘制内容，按钮始终不透明。
"""
import ctypes
import sys

from PySide6.QtCore import (QPointF, QTimer, QPoint, QRectF, Qt, Signal)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QHBoxLayout, QMenu, QPushButton,
                               QVBoxLayout, QWidget)

from . import theme

SIZE_W = 230
VISUAL_H = 168          # 视觉窗高度（卡片+圆环+把手）
CONTROLS_H = 44         # 控制窗高度（按钮行）
CONTROLS_OVERLAP = 0    # 两窗口紧贴不留缝
RING_D = SIZE_W - 92
RING_TOP = 26           # 圆环顶部（视觉窗内，给把手留出空间）
GRIP_SIZE = 26          # 把手区域大小（左上角正方形）

IS_WINDOWS = sys.platform == "win32"

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WM_NCHITTEST = 0x0084
HTTRANSPARENT = -1


def _set_click_through(hwnd: int) -> None:
    """给原生窗口加 WS_EX_LAYERED（配合 Qt 的 TranslucentBackground）。
    注意：不用 WS_EX_TRANSPARENT，因为我们需要接收部分区域的鼠标事件，
    穿透逻辑由 nativeEvent 的 WM_NCHITTEST 处理。"""
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)


class MiniOverlay(QWidget):
    """视觉窗：圆环 + 时间 + 左上角拖拽把手。圆环区域点击穿透。"""

    grip_drag_moved = Signal(QPoint)   # 拖动中（全局坐标）
    grip_drag_finished = Signal()      # 拖动结束

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(SIZE_W, VISUAL_H)
        self._time_text = "--:--"
        self._progress = 0.0
        self._color = theme.ACCENT
        self._opacity = 1.0
        self._drag_offset: QPoint | None = None

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
        """显示后调用：设置 WS_EX_LAYERED 让 WM_NCHITTEST 生效。"""
        if IS_WINDOWS and self.isVisible():
            _set_click_through(int(self.winId()))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if IS_WINDOWS:
            QTimer.singleShot(0, self.enable_click_through)

    # ---------- 拖拽把手（左上角） ----------
    def _in_grip(self, pos: QPoint) -> bool:
        return pos.x() <= GRIP_SIZE and pos.y() <= GRIP_SIZE

    def _in_ring(self, pos: QPoint) -> bool:
        ring_cx = SIZE_W / 2
        ring_cy = RING_TOP + RING_D / 2
        dist_sq = (pos.x() - ring_cx) ** 2 + (pos.y() - ring_cy) ** 2
        return dist_sq <= (RING_D / 2 + 8) ** 2   # 8px 容差

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._in_grip(event.position().toPoint()):
            self._drag_offset = (event.globalPosition().toPoint() - self.pos())

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None:
            new_pos = event.globalPosition().toPoint() - self._drag_offset
            self.move(new_pos)
            self.grip_drag_moved.emit(new_pos)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            self.grip_drag_finished.emit()

    # ---------- 点击穿透（圆环区域透到下层，把手区域正常拖动） ----------
    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_NCHITTEST:
                x = ctypes.c_short(msg.lParam & 0xFFFF).value
                y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                pos = self.mapFromGlobal(QPoint(x, y))
                if self._in_ring(pos):
                    return True, HTTRANSPARENT
                # 把手和其余区域正常处理
        return super().nativeEvent(eventType, message)

    # ---------- 绘制 ----------
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        op = self._opacity
        card = QColor(theme.OVERLAY[0], theme.OVERLAY[1], theme.OVERLAY[2],
                      int(theme.OVERLAY[3] * op))
        p.setPen(Qt.NoPen)
        p.setBrush(card)
        p.drawRoundedRect(QRectF(4, 4, SIZE_W - 8, VISUAL_H - 8), 18, 18)

        # 拖拽把手：左上角竖排三粒圆点
        p.setPen(Qt.NoPen)
        dot = self._fade(QColor(theme.TEXT_DIM))
        p.setBrush(dot)
        for dy in (-7, 0, 7):
            p.drawEllipse(QPointF(13, 26 + dy), 2.5, 2.5)

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
        self._label = label
        self.update()

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

        p.setPen(QColor(theme.TEXT_DIM))
        small = QFont()
        small.setPixelSize(12)
        p.setFont(small)
        p.drawText(QRectF(0, 4, SIZE_W, CONTROLS_H - 8),
                   Qt.AlignHCenter | Qt.AlignVCenter, self._label)
        p.end()
