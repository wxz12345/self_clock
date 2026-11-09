# -*- coding: utf-8 -*-
"""迷你窗：一条紧凑的药丸形计时条（约 236×48），三窗口结构：

- MiniOverlay ：视觉窗（药丸底 + 小圆环 + 时间 + 状态），整窗点击穿透
  （WS_EX_TRANSPARENT），可以直接点击它下面的窗口
- MiniGrip    ：左侧拖拽把手（可交互，右键调透明度），拖动时移动整体
- MiniControls：右侧图标按钮（开始/暂停、放弃、跳过、返回），无自带底色，
  叠在视觉窗的药丸底上

拆三个窗口的原因：Windows 的 WM_NCHITTEST/HTTRANSPARENT 只在同线程窗口间有效，
跨进程的局部穿透做不到；WS_EX_TRANSPARENT 是整窗生效。因此把"可交互部分"
（把手、按钮）各自做成独立窗口，视觉窗保持全穿透。三个窗口大小/位置由
本模块的常量统一决定，主窗口只按 *_OFFSET 摆放。
"""
import ctypes
import sys

from PySide6.QtCore import QPoint, QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import (QActionGroup, QColor, QFont, QFontMetrics,
                           QPainter, QPainterPath, QPen, QPolygonF)
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QMenu, QWidget

from . import theme

SIZE_W = 236            # 整条宽度
VISUAL_H = 48           # 整条高度（三个窗口同高）
GRIP_W = 22             # 左侧拖拽把手宽度
CONTROLS_W = 118        # 右侧按钮区宽度
BTN = 26                # 图标按钮尺寸
RING_D = 26             # 小圆环直径
RING_X = GRIP_W + 2     # 圆环左边缘
TEXT_X = RING_X + RING_D + 9   # 时间文字起点

GRIP_OFFSET = QPoint(0, 0)                          # 相对视觉窗左上角
CONTROLS_OFFSET = QPoint(SIZE_W - CONTROLS_W, 0)

OPACITY_CHOICES = (100, 85, 70, 55)

IS_WINDOWS = sys.platform == "win32"

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20


def _set_click_through(hwnd: int) -> None:
    """给原生窗口加 WS_EX_TRANSPARENT：整窗鼠标事件穿透到下层窗口。"""
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(
        hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED)


def _clamp_opacity(percent: int) -> float:
    return max(0.15, min(1.0, percent / 100.0))


# 透明窗口里 alpha=0 的像素在 Windows 上不接收鼠标；控件底下垫一层
# 几乎看不见的底色，保证整块区域都能点到/拖到
_HIT_ALPHA = 1


class MiniOverlay(QWidget):
    """视觉窗：药丸底 + 小圆环 + 时间 + 状态文字，整窗点击穿透。"""

    moved = Signal(QPoint)   # 位置变化（含系统移动），供其他窗口跟随

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFixedSize(SIZE_W, VISUAL_H)
        self._time_text = "--:--"
        self._state_text = ""
        self._progress = 0.0
        self._color = theme.ACCENT
        self._opacity = 1.0

    def set_display(self, time_text: str, progress: float,
                    phase_key: str) -> None:
        self._time_text = time_text
        self._progress = max(0.0, min(1.0, progress))
        self._color = theme.PHASE_COLORS.get(phase_key, theme.ACCENT)
        self.update()

    def set_state_label(self, label: str) -> None:
        # 去掉前导的 emoji / 符号（如 "⏱ 顺计时中"），小字号下字形不稳定
        text = label.lstrip("⏱ ").strip()
        if text != self._state_text:
            self._state_text = text
            self.update()

    def set_opacity(self, percent: int) -> None:
        self._opacity = _clamp_opacity(percent)
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

    def _fade(self, color: QColor, scale: float = 1.0) -> QColor:
        c = QColor(color)
        c.setAlpha(max(0, min(255, int(c.alpha() * self._opacity * scale))))
        return c

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = VISUAL_H

        # 药丸底：半透明卡 + 一圈细描边
        body = QRectF(1, 1, SIZE_W - 2, h - 2)
        card = QColor(*theme.OVERLAY)
        p.setBrush(self._fade(card))
        p.setPen(QPen(self._fade(QColor(theme.BORDER), 0.9), 1))
        p.drawRoundedRect(body, body.height() / 2, body.height() / 2)

        # 小圆环（底环 + 进度弧）
        ring = QRectF(RING_X, (h - RING_D) / 2, RING_D, RING_D)
        width = 3.6
        track = QPen(self._fade(QColor(theme.BORDER)), width)
        track.setCapStyle(Qt.RoundCap)
        p.setPen(track)
        p.setBrush(Qt.NoBrush)
        p.drawArc(ring.adjusted(width / 2, width / 2, -width / 2, -width / 2),
                  0, 360 * 16)
        if self._progress > 0:
            pen = QPen(self._fade(QColor(self._color)), width)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(ring.adjusted(width / 2, width / 2, -width / 2, -width / 2),
                      90 * 16, int(-360 * self._progress * 16))

        # 时间（两行：大号时间 + 小号状态）；超长（带小时）自动缩小
        avail = (SIZE_W - CONTROLS_W) - TEXT_X + 4
        font = QFont()
        font.setBold(True)
        font.setPixelSize(20)
        while font.pixelSize() > 12 and QFontMetrics(font).horizontalAdvance(
                self._time_text) > avail:
            font.setPixelSize(font.pixelSize() - 1)
        p.setFont(font)
        p.setPen(self._fade(QColor(theme.TEXT)))
        time_rect = QRectF(TEXT_X, 6, avail, 23)
        p.drawText(time_rect, Qt.AlignLeft | Qt.AlignVCenter, self._time_text)

        if self._state_text:
            small = QFont()
            small.setPixelSize(11)
            p.setFont(small)
            p.setPen(self._fade(QColor(self._color)))
            p.drawText(QRectF(TEXT_X, 28, avail, 14),
                       Qt.AlignLeft | Qt.AlignVCenter, self._state_text)
        p.end()


class MiniGrip(QWidget):
    """左侧拖拽把手：可交互的透明小窗口，拖动时移动整个迷你窗；右键调透明度。"""

    drag_moved = Signal(QPoint)   # 新的左上角坐标（把手的左上角）
    drag_finished = Signal()
    opacity_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(GRIP_W, VISUAL_H)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("拖动移动迷你窗；右键调整透明度")
        self._drag_offset: QPoint | None = None
        self._percent = 100
        self._hover = False

    def set_opacity(self, percent: int) -> None:
        self._percent = percent
        self.setWindowOpacity(_clamp_opacity(percent))
        self.update()

    # ---------- 拖动 ----------
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

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    # ---------- 右键：透明度 ----------
    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        title = menu.addAction("迷你窗透明度")
        title.setEnabled(False)
        group = QActionGroup(menu)
        for percent in OPACITY_CHOICES:
            act = menu.addAction(f"{percent}%")
            act.setCheckable(True)
            act.setChecked(percent == self._percent)
            group.addAction(act)
            act.triggered.connect(
                lambda _=False, v=percent: self.opacity_selected.emit(v))
        menu.exec(event.globalPos())

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, _HIT_ALPHA))      # 保证整条把手可点
        p.drawRect(self.rect())
        # 2 列 × 3 行的小点阵
        dot = QColor(theme.TEXT if self._hover else theme.TEXT_DIM)
        dot.setAlpha(210 if self._hover else 130)
        p.setBrush(dot)
        cx, cy = GRIP_W / 2 + 1, VISUAL_H / 2
        for dx in (-3, 3):
            for dy in (-7, 0, 7):
                p.drawEllipse(QPointF(cx + dx, cy + dy), 1.5, 1.5)
        p.end()


class IconButton(QAbstractButton):
    """自绘图标按钮（不依赖字体）：play / pause / cross / skip / expand。"""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.accent: QColor | None = None
        self.setFixedSize(BTN, BTN)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False

    def set_kind(self, kind: str) -> None:
        if kind != self.kind:
            self.kind = kind
            self.update()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        if self._hover or self.isDown():
            bg = QColor(theme.CARD_2)
            bg.setAlpha(255 if self.isDown() else 230)
        else:
            bg = QColor(0, 0, 0, _HIT_ALPHA)
        p.setBrush(bg)
        p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))

        base = self.accent or QColor(theme.TEXT_DIM)
        color = QColor(self.accent or theme.TEXT) if self._hover else QColor(base)
        p.translate((BTN - 24) / 2, (BTN - 24) / 2)     # 图标按 24×24 设计
        p.setBrush(color)
        k = self.kind
        if k == "play":
            p.drawPolygon(QPolygonF([QPointF(9.5, 6.5), QPointF(9.5, 17.5),
                                     QPointF(18, 12)]))
        elif k == "pause":
            p.drawRoundedRect(QRectF(8, 7, 3.2, 10), 1, 1)
            p.drawRoundedRect(QRectF(13, 7, 3.2, 10), 1, 1)
        elif k == "skip":
            p.drawPolygon(QPolygonF([QPointF(7.5, 7), QPointF(7.5, 17),
                                     QPointF(14.5, 12)]))
            p.drawRoundedRect(QRectF(15.5, 7, 2.2, 10), 1, 1)
        else:
            pen = QPen(color, 1.9)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            if k == "cross":                      # 放弃
                p.drawLine(QPointF(8.5, 8.5), QPointF(15.5, 15.5))
                p.drawLine(QPointF(15.5, 8.5), QPointF(8.5, 15.5))
            elif k == "expand":                   # 返回主窗口：向外的双角标
                path = QPainterPath()
                path.moveTo(13, 7)
                path.lineTo(17, 7)
                path.lineTo(17, 11)
                path.moveTo(11, 17)
                path.lineTo(7, 17)
                path.lineTo(7, 13)
                p.drawPath(path)
                p.drawLine(QPointF(8.5, 15.5), QPointF(15.5, 8.5))
        p.end()


class MiniControls(QWidget):
    """右侧按钮区：开始/暂停、放弃、跳过、返回，图标按钮，无自带底色。"""

    primary_requested = Signal()
    abandon_requested = Signal()
    skip_requested = Signal()
    expand_requested = Signal()
    opacity_selected = Signal(int)   # 保留接口（透明度现由把手右键菜单发出）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(CONTROLS_W, VISUAL_H)

        self.btn_primary = IconButton("play")
        self.btn_primary.accent = QColor(theme.ACCENT)
        self.btn_primary.setToolTip("开始专注")
        self.btn_primary.clicked.connect(self.primary_requested.emit)
        self.btn_abandon = IconButton("cross")
        self.btn_abandon.accent = QColor(theme.DANGER)
        self.btn_abandon.setToolTip("放弃本次专注")
        self.btn_abandon.clicked.connect(self.abandon_requested.emit)
        self.btn_skip = IconButton("skip")
        self.btn_skip.setToolTip("跳过休息")
        self.btn_skip.clicked.connect(self.skip_requested.emit)
        self.btn_expand = IconButton("expand")
        self.btn_expand.setToolTip("返回主窗口")
        self.btn_expand.clicked.connect(self.expand_requested.emit)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 12, 0)     # 右侧留出药丸圆角
        row.setSpacing(3)
        row.addStretch(1)
        for b in (self.btn_primary, self.btn_abandon, self.btn_skip,
                  self.btn_expand):
            row.addWidget(b)

    def set_actions(self, primary_text: str, show_primary: bool,
                    show_abandon: bool, show_skip: bool) -> None:
        # 主按钮：运行中显示「暂停」图标，其余（开始/继续）显示「播放」图标
        self.btn_primary.set_kind("pause" if primary_text == "暂停" else "play")
        self.btn_primary.setToolTip(primary_text)
        self.btn_primary.setVisible(show_primary)
        self.btn_abandon.setVisible(show_abandon)
        self.btn_skip.setVisible(show_skip)

    def set_opacity(self, percent: int) -> None:
        self.setWindowOpacity(_clamp_opacity(percent))

    def paintEvent(self, event) -> None:
        pass   # 底色由视觉窗的药丸提供
