# -*- coding: utf-8 -*-
"""专注页：进度环 + 当前任务 + 控制按钮 + 小树与今日进度。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from core.timer import Phase

from . import theme
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
    # 不挂 QGraphicsDropShadowEffect：悬停局部重绘会导致卡片消失（Qt 渲染缺陷），
    # 立体感由 QSS 细边框 + 卡片/背景色差提供
    return frame


NOISE_ITEMS = [("🌧 雨声", "rain"), ("⛈ 雷雨", "thunder"), ("🌊 海浪", "waves"),
               ("🔥 篝火", "fire"), ("🍃 风声", "wind"), ("🐦 鸟鸣", "birds"),
               ("☕ 咖啡馆", "cafe"), ("🟤 棕噪音", "brown")]

DURATION_PRESETS = [15, 25, 30, 45, 60, 90, 120]


class FocusView(QWidget):
    start_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    abandon_requested = Signal()
    skip_break_requested = Signal()
    task_selected = Signal(object)  # task_id 或 None
    category_selected = Signal(str)  # 计时归类
    duration_selected = Signal(int)  # 本次专注时长（分钟）
    mode_selected = Signal(str)      # pomodoro / stopwatch
    stop_requested = Signal()        # 顺计时：停止并记录
    noise_mixer_requested = Signal()
    mini_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._primary_action_name = "start_focus"  # start_focus / start_break / resume
        self._updating_combo = False
        self._updating_category = False
        self._updating_duration = False
        self._updating_mode = False
        self.mode = "pomodoro"

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        # ----- 左：计时器卡片 -----
        left = card()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(24, 22, 24, 22)
        left_layout.setSpacing(12)

        phase_row = QHBoxLayout()
        self.btn_mode_pomo = QPushButton("🍅 番茄")
        self.btn_mode_pomo.setCheckable(True)
        self.btn_mode_pomo.setFixedHeight(30)
        self.btn_mode_pomo.setCursor(Qt.PointingHandCursor)
        self.btn_mode_pomo.clicked.connect(
            lambda: self.mode_selected.emit("pomodoro"))
        self.btn_mode_stop = QPushButton("⏱ 顺计时")
        self.btn_mode_stop.setCheckable(True)
        self.btn_mode_stop.setFixedHeight(30)
        self.btn_mode_stop.setCursor(Qt.PointingHandCursor)
        self.btn_mode_stop.clicked.connect(
            lambda: self.mode_selected.emit("stopwatch"))
        phase_row.addWidget(self.btn_mode_pomo)
        phase_row.addWidget(self.btn_mode_stop)
        phase_row.addStretch(1)
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
        self.duration_label = QLabel("本次专注")
        task_row.addWidget(self.duration_label)
        self.duration_combo = QComboBox()
        self.duration_combo.setEditable(True)
        self.duration_combo.setInsertPolicy(QComboBox.NoInsert)
        for m in DURATION_PRESETS:
            self.duration_combo.addItem(f"{m}", m)
        self.duration_combo.setFixedWidth(76)
        self.duration_combo.setValidator(self._minutes_validator())
        self.duration_combo.currentIndexChanged.connect(self._on_duration_changed)
        self.duration_combo.editTextChanged.connect(self._on_duration_text_changed)
        task_row.addWidget(self.duration_combo)
        self.unit_label = QLabel("分钟")
        task_row.addWidget(self.unit_label)
        task_row.addSpacing(14)
        task_row.addWidget(QLabel("分类"))
        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(96)
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        task_row.addWidget(self.category_combo)
        task_row.addSpacing(14)
        task_row.addWidget(QLabel("当前任务"))
        self.task_combo = QComboBox()
        self.task_combo.setMinimumWidth(200)
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
        self.btn_stop = QPushButton("停止并记录")
        self.btn_stop.setObjectName("primary")
        self.btn_stop.setFixedHeight(42)
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        btn_row.addWidget(self.btn_primary)
        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_stop)
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
    def _minutes_validator(self):
        from PySide6.QtGui import QIntValidator
        v = QIntValidator(1, 180, self)
        return v

    def _on_duration_text_changed(self, text: str) -> None:
        if self._updating_duration:
            return
        try:
            minutes = int(text)
        except ValueError:
            return
        if 1 <= minutes <= 180:
            self.duration_selected.emit(minutes)

    def _on_duration_changed(self, index: int) -> None:
        if self._updating_duration:
            return
        minutes = self.duration_combo.currentData()
        if minutes is None:  # 手动输入的自定义值
            try:
                minutes = int(self.duration_combo.currentText())
            except ValueError:
                return
        if 1 <= int(minutes) <= 180:
            self.duration_selected.emit(int(minutes))

    def set_mode(self, mode: str) -> None:
        """切换 番茄/顺计时 模式（待机时才允许切换）。"""
        self.mode = mode
        self._updating_mode = True
        self.btn_mode_pomo.setChecked(mode == "pomodoro")
        self.btn_mode_stop.setChecked(mode == "stopwatch")
        self._updating_mode = False
        self.duration_label.setVisible(mode == "pomodoro")
        self.duration_combo.setVisible(mode == "pomodoro")
        self.unit_label.setVisible(mode == "pomodoro")
        if mode == "stopwatch":
            self.phase_label.setText("准备开始顺计时")
            self.btn_primary.setText("开始顺计时")
            self.btn_primary.setVisible(True)
            self.btn_pause.setVisible(False)
            self.btn_stop.setVisible(False)
            self.btn_skip.setVisible(False)
            self.btn_abandon.setVisible(False)
            self.ring.set_display("00:00", 0.0, "stopwatch")

    def set_stopwatch(self, elapsed: float, running: bool, paused: bool) -> None:
        total = max(1, elapsed)
        text = self._fmt_elapsed(elapsed)
        progress = min(1.0, elapsed / (45 * 60))
        self.ring.set_display(text, progress, "stopwatch")
        if running:
            self.phase_label.setText("⏱ 顺计时中")
            self.btn_primary.setVisible(False)
            self.btn_stop.setVisible(True)
            self.btn_pause.setText("暂停")
            self.btn_pause.setVisible(True)
            self.btn_abandon.setVisible(True)
        elif paused:
            self.phase_label.setText("⏱ 已暂停")
            self.btn_primary.setText("继续")
            self.btn_primary.setVisible(True)
            self.btn_stop.setVisible(False)
            self.btn_pause.setVisible(False)
            self.btn_abandon.setVisible(True)
        else:
            self.phase_label.setText("准备开始顺计时")
            self.btn_primary.setText("开始顺计时")
            self.btn_primary.setVisible(True)
            self.btn_stop.setVisible(False)
            self.btn_pause.setVisible(False)
            self.btn_abandon.setVisible(False)

    @staticmethod
    def _fmt_elapsed(seconds: float) -> str:
        s = int(seconds)
        if s >= 3600:
            return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
        return f"{s // 60:02d}:{s % 60:02d}"

    def set_duration(self, minutes: int) -> None:
        """外部（设置/初始化）同步显示，不触发信号。"""
        self._updating_duration = True
        index = self.duration_combo.findData(minutes)
        if index >= 0:
            self.duration_combo.setCurrentIndex(index)
        else:
            self.duration_combo.setEditText(str(minutes))
        self._updating_duration = False
        self._updating_mode = False
        self.mode = "pomodoro"

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
        self.tree_stage_label.setStyleSheet(f"color: {theme.GOLD}; font-weight: bold;")
        if today_count >= goal:
            self.goal_label.setStyleSheet(f"color: {theme.ACCENT};")
        else:
            self.goal_label.setStyleSheet("")
