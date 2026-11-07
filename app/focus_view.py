# -*- coding: utf-8 -*-
"""专注页：进度环 + 当前任务 + 控制按钮 + 小树与今日进度。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from core.timer import Phase

from .timer_ring import TimerRing
from .tree_widget import TreeWidget

PHASE_LABELS = {
    (Phase.FOCUS, True, False): "🍅 专注中",
    (Phase.FOCUS, True, True): "⏸ 已暂停",
    (Phase.FOCUS, False, False): "准备开始专注",
    (Phase.SHORT_BREAK, True, False): "☕ 短休息",
    (Phase.SHORT_BREAK, True, True): "⏸ 休息暂停",
    (Phase.SHORT_BREAK, False, False): "该休息了",
    (Phase.LONG_BREAK, True, False): "🌿 长休息",
    (Phase.LONG_BREAK, True, True): "⏸ 休息暂停",
    (Phase.LONG_BREAK, False, False): "该长休了",
}

STAGE_EMOJI = {"种子": "🌱", "幼苗": "🌿", "小树": "🌳", "大树": "🌳"}


def card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    return frame


NOISE_ITEMS = [("🌧 雨声", "rain"), ("⛈ 雷雨", "thunder"), ("🌊 海浪", "waves"),
               ("🔥 篝火", "fire"), ("🍃 风声", "wind"), ("🐦 鸟鸣", "birds"),
               ("☕ 咖啡馆", "cafe"), ("🟤 棕噪音", "brown")]


class FocusView(QWidget):
    start_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    abandon_requested = Signal()
    skip_break_requested = Signal()
    task_selected = Signal(object)  # task_id 或 None
    category_selected = Signal(str)  # 计时归类
    noise_mixer_requested = Signal()
    mini_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._primary_action_name = "start_focus"  # start_focus / start_break / resume
        self._updating_combo = False
        self._updating_category = False

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        # ----- 左：计时器卡片 -----
        left = card()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(24, 22, 24, 22)
        left_layout.setSpacing(12)

        phase_row = QHBoxLayout()
        self.phase_label = QLabel("准备开始专注")
        self.phase_label.setAlignment(Qt.AlignCenter)
        self.phase_label.setObjectName("title")
        phase_row.addStretch(1)
        phase_row.addWidget(self.phase_label)
        phase_row.addStretch(1)
        self.btn_mini = QPushButton("🎯 迷你窗")
        self.btn_mini.setToolTip("显示可拖动的置顶小窗（双击小窗关闭）")
        self.btn_mini.setCursor(Qt.PointingHandCursor)
        self.btn_mini.clicked.connect(self.mini_requested.emit)
        phase_row.addWidget(self.btn_mini)
        left_layout.addLayout(phase_row)

        self.ring = TimerRing()
        self.ring.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self.ring, stretch=1)

        task_row = QHBoxLayout()
        task_row.addStretch(1)
        task_row.addWidget(QLabel("分类"))
        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(96)
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        task_row.addWidget(self.category_combo)
        task_row.addSpacing(16)
        task_row.addWidget(QLabel("当前任务"))
        self.task_combo = QComboBox()
        self.task_combo.setMinimumWidth(220)
        self.task_combo.currentIndexChanged.connect(self._on_task_changed)
        task_row.addWidget(self.task_combo)
        task_row.addStretch(1)
        left_layout.addLayout(task_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_primary = QPushButton("开始专注")
        self.btn_primary.setObjectName("primary")
        self.btn_primary.setFixedHeight(42)
        self.btn_primary.setFixedWidth(150)
        self.btn_primary.clicked.connect(self._on_primary)
        self.btn_pause = QPushButton("暂停")
        self.btn_pause.setFixedHeight(42)
        self.btn_pause.clicked.connect(self.pause_requested.emit)
        self.btn_abandon = QPushButton("放弃")
        self.btn_abandon.setObjectName("danger")
        self.btn_abandon.setFixedHeight(42)
        self.btn_abandon.clicked.connect(self.abandon_requested.emit)
        self.btn_skip = QPushButton("跳过休息")
        self.btn_skip.setFixedHeight(42)
        self.btn_skip.clicked.connect(self.skip_break_requested.emit)
        btn_row.addWidget(self.btn_primary)
        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_skip)
        btn_row.addWidget(self.btn_abandon)
        btn_row.addStretch(1)
        left_layout.addLayout(btn_row)

        noise_row = QHBoxLayout()
        noise_row.addStretch(1)
        self.btn_noise = QPushButton("🎧 白噪音混音器")
        self.btn_noise.setToolTip("多种声音叠加，各自调音量")
        self.btn_noise.setCursor(Qt.PointingHandCursor)
        self.btn_noise.clicked.connect(self.noise_mixer_requested.emit)
        noise_row.addWidget(self.btn_noise)
        noise_row.addStretch(1)
        left_layout.addLayout(noise_row)
        root.addWidget(left, stretch=1)

        # ----- 右：树 + 今日 -----
        right = QVBoxLayout()
        right.setSpacing(20)

        tree_card = card()
        tree_layout = QVBoxLayout(tree_card)
        tree_layout.setContentsMargins(16, 14, 16, 14)
        tree_title = QLabel("我的树")
        tree_title.setObjectName("title")
        tree_title.setAlignment(Qt.AlignCenter)
        tree_layout.addWidget(tree_title)
        self.tree = TreeWidget()
        tree_layout.addWidget(self.tree, stretch=1)
        self.tree_stage_label = QLabel("🌱 种子 · 0 金币")
        self.tree_stage_label.setObjectName("muted")
        self.tree_stage_label.setAlignment(Qt.AlignCenter)
        tree_layout.addWidget(self.tree_stage_label)
        right.addWidget(tree_card, stretch=1)

        today_card = card()
        today_layout = QVBoxLayout(today_card)
        today_layout.setContentsMargins(18, 14, 18, 14)
        today_layout.setSpacing(8)
        today_title = QLabel("今日")
        today_title.setObjectName("title")
        today_layout.addWidget(today_title)
        self.goal_label = QLabel("目标 0/6 🍅")
        self.goal_label.setObjectName("h2")
        self.goal_label.setAlignment(Qt.AlignCenter)
        today_layout.addWidget(self.goal_label)
        self.streak_label = QLabel("🔥 连击 0 天")
        self.streak_label.setObjectName("muted")
        self.streak_label.setAlignment(Qt.AlignCenter)
        today_layout.addWidget(self.streak_label)
        right.addWidget(today_card)

        right_wrap = QWidget()
        right_wrap.setLayout(right)
        right_wrap.setFixedWidth(300)
        root.addWidget(right_wrap)

        self.update_state(Phase.FOCUS, running=False, paused=False)

    # ---------- 交互 ----------
    def _on_primary(self) -> None:
        {"start_focus": self.start_requested,
         "start_break": self.start_requested,
         "resume": self.resume_requested}[self._primary_action_name].emit()

    def _on_category_changed(self, index: int) -> None:
        if self._updating_category:
            return
        self.category_selected.emit(self.category_combo.currentText())

    def set_category_options(self, categories: list, current: str) -> None:
        self._updating_category = True
        self.category_combo.clear()
        self.category_combo.addItems(categories)
        index = self.category_combo.findText(current)
        self.category_combo.setCurrentIndex(index if index >= 0 else 0)
        self._updating_category = False

    def _on_task_changed(self, index: int) -> None:
        if self._updating_combo:
            return
        self.task_selected.emit(self.task_combo.itemData(index))

    # ---------- 由主窗口驱动 ----------
    def update_state(self, phase: Phase, running: bool, paused: bool) -> None:
        self.phase_label.setText(
            PHASE_LABELS.get((phase, running, paused), "准备开始专注"))
        if not running:
            self._primary_action_name = ("start_focus" if phase == Phase.FOCUS
                                         else "start_break")
            self.btn_primary.setText("开始专注" if phase == Phase.FOCUS else "开始休息")
            self.btn_primary.setVisible(True)
            self.btn_pause.setVisible(False)
            self.btn_skip.setVisible(phase.is_break)
            self.btn_skip.setText("跳过休息")
            self.btn_abandon.setVisible(False)
        elif paused:
            self._primary_action_name = "resume"
            self.btn_primary.setText("继续")
            self.btn_primary.setVisible(True)
            self.btn_pause.setVisible(False)
            self.btn_skip.setVisible(False)
            self.btn_abandon.setVisible(phase == Phase.FOCUS)
        else:
            self.btn_primary.setVisible(False)
            self.btn_pause.setVisible(True)
            self.btn_skip.setVisible(phase.is_break)
            self.btn_abandon.setVisible(phase == Phase.FOCUS)

    def set_time(self, time_text: str, progress: float, phase_key: str) -> None:
        self.ring.set_display(time_text, progress, phase_key)

    def set_task_options(self, tasks: list, current_task_id) -> None:
        """tasks: store.get_tasks(include_done=False) 的行列表。"""
        self._updating_combo = True
        self.task_combo.clear()
        self.task_combo.addItem("不关联任务", None)
        for row in tasks:
            mark = "✅ " if row["done"] else ""
            self.task_combo.addItem(
                f"{mark}{row['name']}（{row['completed']}/{row['estimated']}）",
                row["id"])
        index = self.task_combo.findData(current_task_id)
        self.task_combo.setCurrentIndex(index if index >= 0 else 0)
        self._updating_combo = False

    def refresh_gamify(self, coins: int, stage_name: str,
                       today_count: int, goal: int, streak_days: int) -> None:
        stage_emoji = STAGE_EMOJI.get(stage_name, "🌱")
        self.tree_stage_label.setText(f"{stage_emoji} {stage_name} · {coins} 金币")
        self.goal_label.setText(f"目标 {today_count}/{goal} 🍅")
        self.streak_label.setText(f"🔥 连击 {streak_days} 天")
