# -*- coding: utf-8 -*-
"""主窗口：侧栏导航 + 五个页面 + 所有模块的粘合层。

store 的所有写操作都集中在这里调度（视图只发信号），core 模块不依赖 UI。
"""
import csv
import json
import math
import os
import sys
import time
from datetime import date

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtWidgets import (QApplication, QButtonGroup, QDialog,
                               QFileDialog, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from core import autostart, gamify
from core.monitor import FrontendMonitor
from core.reminder import ReminderScheduler
from core.timer import Phase, PomodoroTimer

from . import icons, theme
from .close_dialog import CloseDialog
from .distraction_dialog import DistractionDialog
from .focus_view import FocusView
from .mini_overlay import MiniOverlay
from .noise_mixer import NoiseMixerDialog
from .reminder_popup import ReminderPopup
from .reminders_view import RemindersView
from .settings_view import SettingsView
from .stats_view import StatsView
from .tasks_view import TasksView
from .tray import TrayController

NAV_ITEMS = [("🍅", "专注"), ("📋", "任务"), ("⏰", "提醒"),
             ("📊", "统计"), ("⚙️", "设置")]


def _fmt_ts(ts) -> str:
    if not ts:
        return ""
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


class MainWindow(QMainWindow):
    def __init__(self, store, sound, data_dir: str, assets_dir: str = ""):
        super().__init__()
        self.store = store
        self.sound = sound
        self.data_dir = data_dir
        self.timer = PomodoroTimer()
        self.monitor = FrontendMonitor()
        self.monitor.start(QThread.LowPriority)  # 常驻线程：专注期间采样前台窗口
        self.scheduler = ReminderScheduler(store)
        self.tray = TrayController(icons.load_app_icon(), self)

        self.session_id = None
        self.current_task_id = self._load_current_task()
        self.current_category = self._load_current_category()
        self._pending_reason = None
        self._last_progress = 0.0
        self._really_quit = False
        self.overlay: MiniOverlay | None = None
        self._fg_samples: list[tuple[float, str]] = []  # 专注期间前台进程采样

        self._reminder_timer = QTimer(self)
        self._configure_break_reminder()

        self._build_ui()
        self._connect_signals()
        self._apply_settings_to_runtime()
        self._close_stale_session()
        self.refresh_all()

    # ================= UI 构建 =================
    def _build_ui(self) -> None:
        self.setWindowTitle("自律番茄钟")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumSize(1020, 640)
        self.resize(1120, 700)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(190)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 20, 14, 18)
        side_layout.setSpacing(4)
        logo = QLabel("🍅 自律番茄钟")
        logo.setObjectName("title")
        logo.setStyleSheet("font-size: 18px; letter-spacing: 1px;")
        side_layout.addWidget(logo)
        brand_sub = QLabel("SELF · CONTROL")
        brand_sub.setObjectName("muted2")
        brand_sub.setStyleSheet("letter-spacing: 3px; font-size: 10px; color: %s;"
                                % theme.ACCENT)
        side_layout.addWidget(brand_sub)
        side_layout.addSpacing(16)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = []
        for i, (emoji, name) in enumerate(NAV_ITEMS):
            btn = QPushButton(f"{emoji}  {name}")
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, idx=i: self._switch_page(idx))
            self.nav_group.addButton(btn, i)
            side_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        side_layout.addStretch(1)
        self.sidebar_hint = QLabel("温和记录 · 本地存储")
        self.sidebar_hint.setObjectName("muted2")
        side_layout.addWidget(self.sidebar_hint)
        root.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.focus_view = FocusView()
        self.tasks_view = TasksView()
        self.reminders_view = RemindersView()
        self.stats_view = StatsView(self.store)
        self.settings_view = SettingsView(self.store, self.store.db_path)
        for view in (self.focus_view, self.tasks_view, self.reminders_view,
                     self.stats_view, self.settings_view):
            self.stack.addWidget(view)
        root.addWidget(self.stack, stretch=1)
        self.setCentralWidget(central)
        self.nav_buttons[0].setChecked(True)

    # ================= 信号连接 =================
    def _connect_signals(self) -> None:
        t = self.timer
        t.tick.connect(self._on_tick)
        t.state_changed.connect(self._on_state_changed)
        t.phase_finished.connect(self._on_phase_finished)
        t.focus_abandoned.connect(self._on_focus_abandoned)

        fv = self.focus_view
        fv.start_requested.connect(self._on_start_requested)
        fv.pause_requested.connect(self._do_pause)
        fv.resume_requested.connect(self._do_resume)
        fv.abandon_requested.connect(self._on_abandon_requested)
        fv.skip_break_requested.connect(self._on_skip_break)
        fv.task_selected.connect(self._on_task_selected)
        fv.category_selected.connect(self._on_category_selected)
        fv.duration_selected.connect(self._on_duration_selected)
        fv.noise_mixer_requested.connect(self._open_noise_mixer)
        fv.mini_requested.connect(self._toggle_mini)
        self._refresh_category_options()

        tv = self.tasks_view
        tv.add_task.connect(self._on_add_task)
        tv.toggle_task.connect(self._on_toggle_task)
        tv.delete_task.connect(self._on_delete_task)
        tv.set_current_task.connect(self._on_task_selected)

        rv = self.reminders_view
        rv.create_requested.connect(self._on_create_reminder)
        rv.complete_requested.connect(self._on_complete_reminder)
        rv.snooze_requested.connect(self._on_snooze_reminder)
        rv.delete_requested.connect(self._on_delete_reminder)

        self.scheduler.due.connect(self._on_reminder_due)
        self.monitor.distraction_detected.connect(self._on_blacklist_hit)
        self.monitor.foreground_sample.connect(self._on_fg_sample)

        sv = self.settings_view
        sv.settings_saved.connect(self._on_settings_saved)
        sv.open_data_dir.connect(self._open_data_dir)
        sv.backup_requested.connect(self._on_backup)
        sv.restore_requested.connect(self._on_restore)
        sv.export_csv_requested.connect(self._on_export_csv)
        sv.clear_data_requested.connect(self._on_clear_data)
        sv.theme_changed.connect(self._on_theme_changed)
        sv.autostart_changed.connect(autostart.set_enabled)

        self.tray.act_show.triggered.connect(self.showNormal)
        self.tray.act_toggle.triggered.connect(self._tray_toggle)
        self.tray.act_mini.triggered.connect(self._toggle_mini)
        self.tray.act_quit.triggered.connect(self._quit)

    # ================= 页面切换 =================
    def _switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        # 注意：不要给 stack 挂 QGraphicsOpacityEffect 之类的效果器——
        # 在部分显卡/驱动下会把自绘控件渲染成空白（计时环消失就是这个原因）
        if index == 2:
            self.reminders_view.refresh(self.store.get_reminders())
        elif index == 3:
            self.stats_view.refresh()
        elif index == 1:
            self._refresh_tasks()

    # ================= 番茄钟流转 =================
    def _on_start_requested(self) -> None:
        t = self.timer
        if t.running:
            return
        if t.phase == Phase.FOCUS:
            self.session_id = self.store.start_session(
                self.current_task_id, "focus", t.durations[Phase.FOCUS],
                self.current_category)
            self.monitor.set_scanning(True)
            self.sound.apply_mix(self._load_mix())
        else:
            self.session_id = self.store.start_session(
                None, t.phase.value, t.durations[t.phase])
        t.start_focus() if t.phase == Phase.FOCUS else t.start_break()
        self._refresh_tree()
        self._update_tray()
        self._refresh_overlay()

    def _do_pause(self) -> None:
        self.timer.pause()
        self.sound.pause_noise()

    def _do_resume(self) -> None:
        self.timer.resume()
        self.sound.resume_noise()

    def _on_skip_break(self) -> None:
        t = self.timer
        if t.phase.is_break and t.running:
            elapsed = (t.durations[t.phase] * 60 - t.remaining_seconds()) / 60
            if self.session_id is not None:
                self.store.finish_session(self.session_id, "skipped",
                                          max(0.0, elapsed))
            self.session_id = None
            t.skip_break()
            self._refresh_tree()
            self._update_tray()
        elif t.phase.is_break:
            t.dismiss_break()
        self._refresh_overlay()

    def _load_mix(self) -> dict:
        """混音配置：优先 noise_mix JSON，兼容旧 white_noise 单音色。"""
        raw = self.store.get_setting("noise_mix", "")
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        old = self.store.get_setting("white_noise", "off")
        return {old: 0.45} if old != "off" else {}

    def _open_noise_mixer(self) -> None:
        dialog = NoiseMixerDialog(self.sound, self.store, self)
        dialog.exec()

    def _on_abandon_requested(self) -> None:
        t = self.timer
        if t.phase != Phase.FOCUS or not t.running:
            return
        # 可能从迷你窗/托盘触发：主窗口要先露出来，原因弹窗才可见
        if not self.isVisible():
            self.showNormal()
        was_paused = t.paused
        t.pause()
        dialog = DistractionDialog(self)
        if dialog.exec() == DistractionDialog.Accepted:
            self._pending_reason = (dialog.reason, dialog.note)
            t.abandon_focus()
        else:
            if not was_paused:
                t.resume()

    def _on_focus_abandoned(self, elapsed_min: float) -> None:
        reason, note = self._pending_reason or ("其他", "")
        self._pending_reason = None
        self.store.finish_session(self.session_id, "abandoned", elapsed_min)
        self.store.add_distraction(self.session_id, reason, note, "manual")
        self._flush_app_usage()
        self.session_id = None
        self.monitor.set_scanning(False)
        self.sound.stop_noise()
        self._refresh_tree()
        self._update_tray()
        self._refresh_overlay()

    def _open_data_dir(self) -> None:
        os.startfile(os.path.dirname(self.store.db_path))

    def _on_phase_finished(self, finished: Phase, nxt: Phase,
                           auto_started: bool) -> None:
        if finished == Phase.FOCUS:
            if self.session_id is not None:
                self.store.finish_session(self.session_id, "completed",
                                          self.timer.durations[Phase.FOCUS])
                self._flush_app_usage()
            if self.current_task_id:
                self.store.increment_task_pomodoro(self.current_task_id)
            self.store.add_coins(gamify.COINS_PER_POMODORO, "完成番茄")
            self.sound.play("bell")
            self.sound.stop_noise()
            self.monitor.set_scanning(False)
            self.tray.notify("🍅 番茄完成！", "干得漂亮，休息一下吧")
            self._check_daily_goal()
        else:
            if self.session_id is not None:
                self.store.finish_session(self.session_id, "completed",
                                          self.timer.durations[finished])
            self.sound.play("chime")
            self.tray.notify("休息结束", "准备好了就开始下一个番茄吧")
        self.session_id = None
        if auto_started:
            self.session_id = self.store.start_session(
                None, nxt.value, self.timer.durations[nxt])
        self._refresh_tasks()
        self._refresh_gamify()
        self._refresh_tree()
        self._update_tray()
        self._refresh_overlay()

    @staticmethod
    def _fmt_remaining(seconds: float) -> str:
        """向上取整：开始后整整 1 秒内都显示满时长，更新节奏与墙钟秒界对齐。"""
        whole = max(0, math.ceil(seconds))
        return f"{whole // 60:02d}:{whole % 60:02d}"

    def _on_tick(self, remaining: float, progress: float) -> None:
        self._last_progress = progress
        text = self._fmt_remaining(remaining)
        self.focus_view.set_time(text, progress, self.timer.phase.value)
        if self.timer.running:
            self.focus_view.tree.set_state(self._tree_stage(), progress, True)
        if self.overlay is not None and self.overlay.isVisible():
            self.overlay.set_display(text, progress, self.timer.phase.value,
                                     True, self._mini_state_label(self.timer))
        self._update_tray(text)

    @staticmethod
    def _mini_state_label(t: PomodoroTimer) -> str:
        if t.running:
            return "专注中" if t.phase == Phase.FOCUS else "休息中"
        if t.paused:
            return "已暂停"
        return "待机"

    def _on_state_changed(self) -> None:
        t = self.timer
        self.focus_view.update_state(t.phase, t.running, t.paused)
        if not t.running:
            planned = t.durations[t.phase] * 60
            self.focus_view.set_time(self._fmt_remaining(planned),
                                     0.0, t.phase.value)
        self._refresh_tree()
        self._update_tray()
        self._refresh_overlay()

    # ================= 迷你窗 =================
    def _toggle_mini(self) -> None:
        if self.overlay is None:
            self.overlay = MiniOverlay()
            self.overlay.drag_finished.connect(self._save_mini_pos)
            self.overlay.primary_requested.connect(self._tray_toggle)
            self.overlay.abandon_requested.connect(self._on_abandon_requested)
            self.overlay.skip_requested.connect(self._on_skip_break)
            self.overlay.expand_requested.connect(self._expand_mini)
        if self.overlay.isVisible():
            self._save_mini_pos()
            self.overlay.hide()
            self.tray.act_mini.setText("显示迷你窗")
        else:
            pos = self._load_mini_pos()
            if pos:
                self.overlay.move(pos[0], pos[1])
            else:
                # 首次打开默认屏幕正中（之后拖动位置自动记忆）
                screen = QApplication.primaryScreen().availableGeometry()
                self.overlay.move(
                    screen.left() + (screen.width() - self.overlay.width()) // 2,
                    screen.top() + (screen.height() - self.overlay.height()) // 2)
            self._refresh_overlay()
            self.overlay.show()
            # 迷你模式接管：主窗口隐藏，控制全部在迷你窗上进行
            self.hide()
            self.tray.act_mini.setText("隐藏迷你窗")

    def _expand_mini(self) -> None:
        """从迷你模式返回主窗口。"""
        if self.overlay is not None:
            self._save_mini_pos()
            self.overlay.hide()
            self.tray.act_mini.setText("显示迷你窗")
        self.showNormal()

    def _refresh_overlay(self) -> None:
        """按当前计时器状态刷新迷你窗的时间与按钮（所有状态变化后调用）。"""
        if self.overlay is None:
            return
        t = self.timer
        if t.running:
            text = self._fmt_remaining(t.remaining_seconds())
            progress = self._last_progress
        elif t.paused:
            text = self._fmt_remaining(t.remaining_seconds())
            progress = self._last_progress
        else:
            planned = t.durations[t.phase] * 60
            text = self._fmt_remaining(planned)
            progress = 0.0
        self.overlay.set_display(text, progress, t.phase.value, t.running,
                                 self._mini_state_label(t))
        # 按钮状态（与专注页 update_state 一致的映射）
        if not t.running:
            primary = "开始专注" if t.phase == Phase.FOCUS else "开始休息"
            show_primary, show_abandon, show_skip = True, False, t.phase.is_break
        elif t.paused:
            primary, show_primary = "继续", True
            show_abandon, show_skip = t.phase == Phase.FOCUS, False
        else:
            primary, show_primary = "暂停", True
            show_abandon, show_skip = t.phase == Phase.FOCUS, t.phase.is_break
        self.overlay.set_actions(primary, show_primary, show_abandon, show_skip)

    def _save_mini_pos(self) -> None:
        if self.overlay is not None:
            self.store.set_setting(
                "mini_pos", f"{self.overlay.x()},{self.overlay.y()}")

    def _load_mini_pos(self):
        raw = self.store.get_setting("mini_pos", "")
        try:
            x, y = raw.split(",")
            return int(float(x)), int(float(y))
        except (ValueError, TypeError):
            return None

    # ================= 游戏化 =================
    def _tree_stage(self) -> int:
        return gamify.tree_stage(self.store.get_coins())[0]

    def _refresh_tree(self) -> None:
        t = self.timer
        grow = self._last_progress if (t.running and t.phase == Phase.FOCUS) else 0.0
        self.focus_view.tree.set_state(self._tree_stage(), grow, t.running)

    def _refresh_gamify(self) -> None:
        coins = self.store.get_coins()
        _, stage_name = gamify.tree_stage(coins)
        goal = self.store.get_int("daily_goal", 6)
        daily = self.store.daily_pomodoros(400)
        today_count = self.store.today_pomodoros()
        self.focus_view.refresh_gamify(
            coins, stage_name, today_count, goal,
            gamify.streak(daily, goal))

    def _check_daily_goal(self) -> None:
        today = date.today().isoformat()
        if self.store.get_setting("last_goal_date") == today:
            return
        if self.store.today_pomodoros() >= self.store.get_int("daily_goal", 6):
            self.store.set_setting("last_goal_date", today)

    # ================= 任务 =================
    def _refresh_tasks(self) -> None:
        tasks = self.store.get_tasks(include_done=True)
        self.tasks_view.refresh(tasks, self.current_task_id)
        self.focus_view.set_task_options(
            [t for t in tasks if not t["done"]], self.current_task_id)

    def _on_add_task(self, name: str, estimated: int) -> None:
        self.store.add_task(name, estimated)
        self._refresh_tasks()

    def _on_toggle_task(self, task_id: int, done: bool) -> None:
        self.store.set_task_done(task_id, done)
        if done and self.current_task_id == task_id:
            self._on_task_selected(None)
        else:
            self._refresh_tasks()

    def _on_delete_task(self, task_id: int) -> None:
        confirm = QMessageBox.question(
            self, "删除任务", "确定删除这个任务吗？已记录的番茄数也会一并删除。")
        if confirm == QMessageBox.Yes:
            self.store.delete_task(task_id)
            if self.current_task_id == task_id:
                self._on_task_selected(None)
            else:
                self._refresh_tasks()

    def _on_task_selected(self, task_id) -> None:
        self.current_task_id = task_id
        self.store.set_setting("current_task", "" if task_id is None else task_id)
        self._refresh_tasks()

    def _load_current_task(self):
        raw = self.store.get_setting("current_task", "")
        try:
            return int(raw) if raw else None
        except ValueError:
            return None

    # ================= 计时归类 =================
    def _load_current_category(self) -> str:
        return self.store.get_setting("last_category", "科研")

    def _refresh_category_options(self) -> None:
        try:
            categories = json.loads(
                self.store.get_setting("categories", "[]")) or ["科研"]
        except json.JSONDecodeError:
            categories = ["科研"]
        self.focus_view.set_category_options(categories, self.current_category)

    def _on_category_selected(self, category: str) -> None:
        self.current_category = category
        self.store.set_setting("last_category", category)
        # 程序化修改归类时同步下拉显示（combo 自身触发的场景下无操作）
        index = self.focus_view.category_combo.findText(category)
        if index >= 0 and self.focus_view.category_combo.currentIndex() != index:
            self.focus_view.category_combo.blockSignals(True)
            self.focus_view.category_combo.setCurrentIndex(index)
            self.focus_view.category_combo.blockSignals(False)

    def _on_duration_selected(self, minutes: int) -> None:
        """专注页手动设置"本次专注"时长：立即反映到倒计时
        （运行/暂停中保留已专注部分；设置页默认值不受影响）。"""
        self.timer.set_focus_minutes(minutes)
        if not self.timer.running and not self.timer.paused:
            planned = minutes * 60
            self.focus_view.set_time(
                self._fmt_remaining(planned), 0.0, Phase.FOCUS.value)
        if self.overlay is not None and self.overlay.isVisible():
            self._refresh_overlay()

    # ================= 外观 / 提醒 =================
    def _on_theme_changed(self, name: str) -> None:
        theme.set_theme(name)
        app = QApplication.instance()
        app.setPalette(theme.build_palette())
        app.setStyleSheet(theme.build_qss())
        for widget in app.allWidgets():
            widget.update()
        self.store.set_setting("theme", name)

    def _configure_break_reminder(self) -> None:
        enabled = self.store.get_int("break_reminder_enabled", 0) == 1
        minutes = max(5, self.store.get_int("break_reminder_min", 60))
        self._reminder_timer.stop()
        if enabled:
            self._reminder_timer.setInterval(minutes * 60 * 1000)
            self._reminder_timer.timeout.connect(self._fire_break_reminder)
            self._reminder_timer.start()

    def _fire_break_reminder(self) -> None:
        text = self.store.get_setting("break_reminder_text", "")
        self.tray.notify("⏰ 久坐提醒", text or "站起来活动活动，记得多喝水 🚰")
        self.sound.play("chime")

    # ================= 提醒 =================
    def _on_create_reminder(self, values: dict) -> None:
        self.store.add_reminder(values["title"], values["event_ts"],
                                values["location"], values["note"],
                                values["remind_ts"])
        self.reminders_view.refresh(self.store.get_reminders())

    def _on_complete_reminder(self, reminder_id: int) -> None:
        self.store.complete_reminder(reminder_id)
        self.reminders_view.refresh(self.store.get_reminders())

    def _on_snooze_reminder(self, reminder_id: int) -> None:
        self.store.snooze_reminder(reminder_id, 300)
        self.reminders_view.refresh(self.store.get_reminders())

    def _on_delete_reminder(self, reminder_id: int) -> None:
        self.store.delete_reminder(reminder_id)
        self.reminders_view.refresh(self.store.get_reminders())

    def _on_reminder_due(self, reminder: dict) -> None:
        self.sound.play("reminder")
        when = "已错过" if reminder.get("missed") else "时间到"
        self.tray.notify(f"⏰ {when}：{reminder['title']}",
                         (f"📍 {reminder['location']}\n" if reminder.get("location")
                          else "") + "点击弹窗处理")
        popup = ReminderPopup(reminder, self)
        popup.exec()
        if popup.action == "done":
            self.store.complete_reminder(reminder["id"])
        elif popup.action == "snooze":
            self.store.snooze_reminder(reminder["id"], 300)
        self.reminders_view.refresh(self.store.get_reminders())

    # ================= 黑名单 / 应用使用 =================
    def _on_fg_sample(self, process_name: str) -> None:
        """专注会话期间（含暂停）的前台进程采样，用于应用使用统计。"""
        if self.session_id is not None:
            self._fg_samples.append((time.time(), process_name))

    def _flush_app_usage(self) -> None:
        """把采样聚合成每个进程的累计使用时长写入数据库。"""
        if not self._fg_samples or self.session_id is None:
            self._fg_samples = []
            return
        # 自身进程归类为应用名
        own_exe = os.path.basename(sys.executable).lower()
        samples = self._fg_samples
        avg_gap = (samples[-1][0] - samples[0][0]) / max(1, len(samples) - 1)
        now = time.time()
        agg: dict[str, float] = {}
        for i, (t0, name) in enumerate(samples):
            t1 = samples[i + 1][0] if i + 1 < len(samples) \
                else min(now, t0 + max(avg_gap * 2, 1.0))
            if name.lower() in ("pythonw.exe", "python.exe", own_exe):
                name = "自律番茄钟"
            agg[name] = agg.get(name, 0.0) + max(0.0, t1 - t0)
        for name, seconds in agg.items():
            if seconds >= 1.0:
                self.store.add_app_usage(self.session_id, name, seconds)
        self._fg_samples = []

    def _on_blacklist_hit(self, process_name: str) -> None:
        """黑名单命中：静默落库（统计页可见），不弹系统通知。"""
        if not (self.timer.running and self.timer.phase == Phase.FOCUS):
            return
        self.store.add_distraction(self.session_id,
                                   f"黑名单程序：{process_name}", "", "blacklist")

    # ================= 设置 =================
    def _apply_settings_to_runtime(self) -> None:
        s = self.store
        self.timer.configure(s.get_int("work_min", 45), s.get_int("short_break_min", 5),
                             s.get_int("long_break_min", 15),
                             s.get_int("rounds_before_long", 4),
                             s.get_int("auto_start_breaks", 1) == 1)
        self.focus_view.set_duration(int(self.timer.durations[Phase.FOCUS]))
        self.sound.enabled = s.get_int("sound_enabled", 1) == 1
        self.monitor.set_blacklist(s.get_blacklist())

    def _on_settings_saved(self, payload: dict) -> None:
        for key, value in payload.items():
            if key == "blacklist":
                self.store.set_blacklist(value)
            else:
                self.store.set_setting(key, value)
        self._apply_settings_to_runtime()
        # 分类可能被编辑：刷新下拉，失效的当前归类回退到第一项
        try:
            categories = json.loads(self.store.get_setting("categories", "[]"))
        except json.JSONDecodeError:
            categories = []
        if categories and self.current_category not in categories:
            self.current_category = categories[0]
            self.store.set_setting("last_category", self.current_category)
        self._refresh_category_options()
        self._configure_break_reminder()
        self._refresh_gamify()
        self._on_state_changed()

    # ================= 托盘 / 窗口 =================
    def _update_tray(self, remaining_text: str | None = None) -> None:
        t = self.timer
        if t.running:
            if remaining_text is None:
                remaining_text = self._fmt_remaining(t.remaining_seconds())
            label = "专注中" if t.phase == Phase.FOCUS else "休息中"
            self.tray.update_timer_tooltip(f"自律番茄钟 - {label} 剩余 {remaining_text}")
            self.tray.act_toggle.setText("暂停")
        elif t.paused:
            self.tray.update_timer_tooltip("自律番茄钟 - 已暂停")
            self.tray.act_toggle.setText("继续")
        else:
            self.tray.update_timer_tooltip("自律番茄钟 - 待机中")
            self.tray.act_toggle.setText("开始专注")

    def _tray_toggle(self) -> None:
        t = self.timer
        if t.running:
            self._do_pause()
        elif t.paused:
            self._do_resume()
        else:
            self._on_start_requested()

    # ================= 关闭 / 退出 =================
    def closeEvent(self, event) -> None:
        """点 ✕ 的行为由 close_action 设置决定：ask / tray / exit。"""
        if self._really_quit:
            event.accept()
            return
        action = self.store.get_setting("close_action", "ask")
        if action == "ask":
            dialog = CloseDialog(self)
            if dialog.exec() != QDialog.Accepted:
                event.ignore()
                return
            action = dialog.action
            if dialog.remember:
                self.store.set_setting("close_action", action)
        if action == "tray":
            event.ignore()
            self.hide()          # 不再弹托盘提示，专注安静进行
            return
        # 直接退出
        if not self._confirm_quit():
            event.ignore()
            return
        self._teardown()
        self._really_quit = True
        event.accept()
        QApplication.quit()

    def _quit(self) -> None:
        if not self._confirm_quit():
            return
        self._teardown()
        self._really_quit = True
        self.close()
        QApplication.quit()

    def _confirm_quit(self) -> bool:
        """退出前若有专注在进行，确认并记为分心。返回是否允许退出。"""
        t = self.timer
        if t.running and t.phase == Phase.FOCUS:
            answer = QMessageBox.question(
                self, "退出确认",
                "专注还在进行中，确定要放弃并退出吗？（会记为一次分心）")
            if answer != QMessageBox.Yes:
                return False
            planned_sec = t.durations[Phase.FOCUS] * 60
            elapsed_min = max(0.0, (planned_sec - t.remaining_seconds()) / 60)
            self.store.finish_session(self.session_id, "abandoned", elapsed_min)
            self.store.add_distraction(self.session_id, "退出应用", "", "manual")
            self._flush_app_usage()
        return True

    def _teardown(self) -> None:
        self.sound.stop_noise()
        self._save_mini_pos()
        if self.overlay is not None:
            self.overlay.hide()
        self.monitor.stop()

    # ================= 备份 / 恢复 / 导出 =================
    def _main_py_path(self) -> str:
        return os.path.join(os.path.dirname(self.data_dir), "main.py")

    def _on_backup(self) -> None:
        from datetime import datetime
        suggested = os.path.join(
            os.path.expanduser("~"), "Desktop",
            f"selfclock_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db")
        path, _ = QFileDialog.getSaveFileName(
            self, "备份数据", suggested, "SQLite 数据库 (*.db)")
        if not path:
            return
        self.store.backup_to(path)

    def _on_restore(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择备份文件", os.path.expanduser("~"),
            "SQLite 数据库 (*.db)")
        if not path:
            return
        answer = QMessageBox.warning(
            self, "恢复备份",
            "恢复将覆盖当前全部数据，并重启应用。\n"
            f"备份文件：{os.path.basename(path)}\n\n确定继续吗？",
            QMessageBox.Yes | QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        self.sound.stop_noise()
        self.monitor.stop()
        self.store.restore_from(path)
        from PySide6.QtCore import QProcess
        QProcess.startDetached(sys.executable, [self._main_py_path()])
        self._really_quit = True
        QApplication.quit()

    def _on_clear_data(self) -> None:
        """按类清空数据（清除测试数据用），带勾选与二次确认。"""
        from PySide6.QtWidgets import QCheckBox, QDialog, QVBoxLayout
        dialog = QDialog(self)
        dialog.setWindowTitle("清空数据")
        dialog.setMinimumWidth(360)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(8)
        info = QLabel("选择要删除的记录（不可恢复，建议先备份）：")
        layout.addWidget(info)
        cb_records = QCheckBox("专注与分心记录")
        cb_records.setChecked(True)
        cb_usage = QCheckBox("应用使用记录")
        cb_usage.setChecked(True)
        cb_coins = QCheckBox("金币与连击（重置为 0）")
        cb_coins.setChecked(True)
        cb_tasks = QCheckBox("任务列表")
        cb_tasks.setChecked(True)
        for cb in (cb_records, cb_usage, cb_coins, cb_tasks):
            layout.addWidget(cb)
        buttons = QHBoxLayout()
        cancel = QPushButton("取消")
        cancel.clicked.connect(dialog.reject)
        ok = QPushButton("确认清空")
        ok.setObjectName("primary")
        ok.clicked.connect(dialog.accept)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

        if dialog.exec() != QDialog.Accepted:
            return
        flags = (cb_records.isChecked(), cb_usage.isChecked(),
                 cb_coins.isChecked(), cb_tasks.isChecked())
        if not any(flags):
            return
        answer = QMessageBox.warning(
            self, "确认清空",
            "所选记录将被永久删除，确定继续吗？",
            QMessageBox.Yes | QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        self.store.clear_records(*flags)
        self.current_task_id = self._load_current_task()
        self.refresh_all()
        self.stats_view.refresh()

    def _on_export_csv(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择导出位置")
        if not folder:
            return
        session_path = os.path.join(folder, "专注会话记录.csv")
        with open(session_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["编号", "类型", "开始时间", "结束时间",
                             "计划(分钟)", "实际(分钟)", "状态", "任务"])
            for row in self.store.sessions_for_export():
                writer.writerow([
                    row["id"], row["type"],
                    _fmt_ts(row["start_ts"]), _fmt_ts(row["end_ts"]),
                    row["planned_min"], row["actual_min"], row["status"],
                    row["task_name"]])
        distraction_path = os.path.join(folder, "分心记录.csv")
        with open(distraction_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["编号", "会话编号", "时间", "原因", "备注", "来源"])
            for row in self.store.distractions_for_export():
                writer.writerow([row["id"], row["session_id"],
                                 _fmt_ts(row["ts"]), row["reason"],
                                 row["note"], row["source"]])

    # ================= 其他 =================
    def _close_stale_session(self) -> None:
        """上次异常退出遗留的 running 会话，标记为放弃。"""
        stale = self.store.open_running_session()
        if stale:
            self.store.finish_session(stale["id"], "abandoned", 0.0)

    def refresh_all(self) -> None:
        self._refresh_tasks()
        self._refresh_gamify()
        self._refresh_tree()
        self._update_tray()
        self.reminders_view.refresh(self.store.get_reminders())
        self.stats_view.refresh()
        self._on_state_changed()
