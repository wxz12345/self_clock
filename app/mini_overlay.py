# -*- coding: utf-8 -*-
"""置顶迷你窗：无边框、始终置顶、可拖动的小控制窗。

迷你模式下主窗口隐藏，开始/暂停/放弃/跳过全部在迷你窗上操作；
双击背景或点 ⤢ 返回主窗口。位置在拖动结束时通知主窗口持久化。
"""
from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from . import theme

SIZE_W = 190
SIZE_H = 216


class MiniOverlay(QWidget):
    primary_requested = Signal()   # 开始/暂停/继续
    abandon_requested = Signal()
    skip_requested = Signal()
    expand_requested = Signal()    # 返回主窗口
    drag_finished = Signal()       # 拖动结束（主窗口保存位置）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(SIZE_W, SIZE_H)
        self._time_text = "--:--"
        self._label = "待机"
        self._progress = 0.0
        self._color = theme.ACCENT
        self._drag_offset: QPoint | None = None

        # ----- 控制按钮 -----
        self.btn_primary = QPushButton("开始专注")
        self.btn_primary.setObjectName("primary")
        self.btn_primary.setFixedHeight(30)
        self.btn_primary.clicked.connect(self.primary_requested.emit)
        self.btn_abandon = QPushButton("放弃")
        self.btn_abandon.setObjectName("danger")
        self.btn_abandon.setFixedHeight(30)
        self.btn_abandon.clicked.connect(self.abandon_requested.emit)
        self.btn_skip = QPushButton("跳过")
        self.btn_skip.setFixedHeight(30)
        self.btn_skip.clicked.connect(self.skip_requested.emit)
        self.btn_expand = QPushButton("⤢")
        self.btn_expand.setToolTip("返回主窗口（也可以双击迷你窗背景）")
        self.btn_expand.setFixedHeight(30)
        self.btn_expand.setFixedWidth(34)
        self.btn_expand.clicked.connect(self.expand_requested.emit)

        row = QHBoxLayout()
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(6)
        row.addWidget(self.btn_primary, stretch=1)
        row.addWidget(self.btn_abandon)
        row.addWidget(self.btn_skip)
        row.addWidget(self.btn_expand)

        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(8)
        layout.addStretch(1)          # 圆环区域（自绘）
        layout.addLayout(row)

    def set_display(self, time_text: str, progress: float, phase_key: str,
                    running: bool, label: str) -> None:
        self._time_text = time_text
        self._progress = max(0.0, min(1.0, progress))
        self._color = theme.PHASE_COLORS.get(phase_key, theme.ACCENT)
        self._label = label
        self.update()

    def set_actions(self, primary_text: str, show_primary: bool,
                    show_abandon: bool, show_skip: bool) -> None:
        self.btn_primary.setText(primary_text)
        self.btn_primary.setVisible(show_primary)
        self.btn_abandon.setVisible(show_abandon)
        self.btn_skip.setVisible(show_skip)

    # ---------- 拖动（按钮以外区域） ----------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            self.drag_finished.emit()

    def mouseDoubleClickEvent(self, event) -> None:
        self.expand_requested.emit()

    # ---------- 绘制 ----------
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # 半透明圆角卡片（随主题）
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(*theme.OVERLAY))
        p.drawRoundedRect(QRectF(4, 4, SIZE_W - 8, SIZE_H - 8), 18, 18)

        ring_rect = QRectF(28, 16, SIZE_W - 56, SIZE_W - 56)
        track = QPen(QColor(theme.CARD_2), 6)
        track.setCapStyle(Qt.RoundCap)
        p.setPen(track)
        p.drawArc(ring_rect, 0, 360 * 16)
        if self._progress > 0:
            pen = QPen(QColor(self._color), 6)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(ring_rect, 90 * 16, int(-360 * self._progress * 16))

        p.setPen(QColor(theme.TEXT))
        font = QFont()
        font.setPixelSize(24)
        font.setBold(True)
        p.setFont(font)
        # 时间严格画在圆环正中央
        p.drawText(ring_rect, Qt.AlignHCenter | Qt.AlignVCenter,
                   self._time_text)
        p.setPen(QColor(theme.TEXT_DIM))
        small = QFont()
        small.setPixelSize(12)
        p.setFont(small)
        p.drawText(QRectF(0, ring_rect.bottom() + 2, SIZE_W, 20),
                   Qt.AlignHCenter | Qt.AlignVCenter, self._label)
        p.end()
