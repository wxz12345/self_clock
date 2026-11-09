# -*- coding: utf-8 -*-
"""设置页：番茄时长、每日目标、声音、黑名单。"""
import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QPushButton, QScrollArea, QSpinBox,
                               QVBoxLayout, QWidget)


CLOSE_OPTIONS = [("每次询问", "ask"), ("最小化到托盘", "tray"), ("直接退出", "exit")]
THEME_OPTIONS = [("深色", "dark"), ("浅色", "light")]


class SettingsView(QWidget):
    settings_saved = Signal(dict)      # 全部设置
    open_data_dir = Signal()
    backup_requested = Signal()
    restore_requested = Signal()
    export_csv_requested = Signal()
    clear_data_requested = Signal()
    theme_changed = Signal(str)        # dark / light
    autostart_changed = Signal(bool)

    def __init__(self, store, data_dir: str, parent=None):
        super().__init__(parent)
        self._store = store
        self._data_dir = data_dir

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)

        root = QVBoxLayout(body)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("设置")
        title.setObjectName("title")
        root.addWidget(title)

        # ----- 番茄时长 -----
        timing_card = QFrame()
        timing_card.setObjectName("card")
        timing_layout = QVBoxLayout(timing_card)
        timing_layout.setContentsMargins(18, 14, 18, 14)
        timing_title = QLabel("番茄时长（分钟）")
        timing_title.setObjectName("title")
        timing_layout.addWidget(timing_title)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)

        self.work_spin = QSpinBox()
        self.work_spin.setRange(5, 180)
        self.short_spin = QSpinBox()
        self.short_spin.setRange(1, 60)
        self.long_spin = QSpinBox()
        self.long_spin.setRange(5, 90)
        self.rounds_spin = QSpinBox()
        self.rounds_spin.setRange(2, 8)
        self.goal_spin = QSpinBox()
        self.goal_spin.setRange(1, 20)
        for i, (label, spin, tip) in enumerate([
                ("专注", self.work_spin, "一个番茄的时长"),
                ("短休息", self.short_spin, "每个番茄后的小憩"),
                ("长休息", self.long_spin, "完成一轮后的长休"),
                ("长休间隔", self.rounds_spin, "每完成几个番茄进长休"),
                ("每日目标", self.goal_spin, "每天想完成的番茄数")]):
            spin.setFixedWidth(90)
            box = QVBoxLayout()
            row_label = QLabel(label)
            row_label.setObjectName("muted2")
            box.addWidget(spin)
            box.addWidget(row_label)
            grid.addLayout(box, i // 3, i % 3)
        timing_layout.addLayout(grid)
        root.addWidget(timing_card)

        # ----- 外观 -----
        theme_card = QFrame()
        theme_card.setObjectName("card")
        theme_layout = QVBoxLayout(theme_card)
        theme_layout.setContentsMargins(18, 14, 18, 14)
        theme_title = QLabel("外观")
        theme_title.setObjectName("title")
        theme_layout.addWidget(theme_title)
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("主题"))
        self.theme_combo = QComboBox()
        for label, key in THEME_OPTIONS:
            self.theme_combo.addItem(label, key)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_combo)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch(1)
        theme_layout.addLayout(theme_row)
        root.addWidget(theme_card)

        # ----- 行为 -----
        behavior_card = QFrame()
        behavior_card.setObjectName("card")
        behavior_layout = QVBoxLayout(behavior_card)
        behavior_layout.setContentsMargins(18, 14, 18, 14)
        behavior_title = QLabel("行为")
        behavior_title.setObjectName("title")
        behavior_layout.addWidget(behavior_title)
        self.sound_check = QCheckBox("提示音（专注/休息结束时）")
        self.auto_break_check = QCheckBox("专注结束后自动开始休息")
        self.autostart_check = QCheckBox("开机自动启动（写入注册表 Run 项，默认关闭）")
        self.autostart_check.toggled.connect(self.autostart_changed.emit)
        self.update_check = QCheckBox("启动时检查新版本（联网访问 GitHub，只读，默认关闭）")
        behavior_layout.addWidget(self.sound_check)
        behavior_layout.addWidget(self.auto_break_check)
        behavior_layout.addWidget(self.autostart_check)
        behavior_layout.addWidget(self.update_check)
        close_row = QHBoxLayout()
        close_label = QLabel("点击窗口 ✕ 关闭时")
        close_label.setObjectName("muted2")
        self.close_combo = QComboBox()
        for label, key in CLOSE_OPTIONS:
            self.close_combo.addItem(label, key)
        close_row.addWidget(close_label)
        close_row.addWidget(self.close_combo)
        close_row.addStretch(1)
        behavior_layout.addLayout(close_row)

        # 久坐提醒
        reminder_row = QHBoxLayout()
        self.reminder_check = QCheckBox("规律性久坐提醒，每")
        self.reminder_min_spin = QSpinBox()
        self.reminder_min_spin.setRange(15, 240)
        self.reminder_min_spin.setSuffix(" 分钟")
        reminder_row.addWidget(self.reminder_check)
        reminder_row.addWidget(self.reminder_min_spin)
        reminder_row.addStretch(1)
        behavior_layout.addLayout(reminder_row)
        self.reminder_text_edit = QLineEdit()
        self.reminder_text_edit.setPlaceholderText("提醒内容，如：站起来活动活动，记得多喝水 🚰")
        behavior_layout.addWidget(self.reminder_text_edit)
        root.addWidget(behavior_card)

        # ----- 计时分类 -----
        category_card = QFrame()
        category_card.setObjectName("card")
        category_layout = QVBoxLayout(category_card)
        category_layout.setContentsMargins(18, 14, 18, 14)
        category_title = QLabel("计时分类")
        category_title.setObjectName("title")
        category_layout.addWidget(category_title)
        category_hint = QLabel("专注页可选的归类（逗号分隔，保存后生效）：")
        category_hint.setObjectName("muted2")
        category_layout.addWidget(category_hint)
        self.categories_edit = QLineEdit()
        category_layout.addWidget(self.categories_edit)
        root.addWidget(category_card)

        # ----- 黑名单 -----
        blacklist_card = QFrame()
        blacklist_card.setObjectName("card")
        bl_layout = QVBoxLayout(blacklist_card)
        bl_layout.setContentsMargins(18, 14, 18, 14)
        bl_title = QLabel("分心程序黑名单")
        bl_title.setObjectName("title")
        bl_layout.addWidget(bl_title)
        bl_hint = QLabel("填写进程名关键词，专注期间检测到这些程序位于前台时提醒并记录。"
                         "如：steam、cloudmusic、bilibili（温和模式：只提醒记录，不会关闭程序）")
        bl_hint.setObjectName("muted2")
        bl_hint.setWordWrap(True)
        bl_layout.addWidget(bl_hint)
        self.blacklist_list = QListWidget()
        self.blacklist_list.setFixedHeight(120)
        bl_layout.addWidget(self.blacklist_list)
        bl_row = QHBoxLayout()
        self.keyword_edit = QLineEdit()
        self.keyword_edit.setPlaceholderText("进程名关键词，如 steam")
        self.keyword_edit.returnPressed.connect(self._add_keyword)
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add_keyword)
        del_btn = QPushButton("删除选中")
        del_btn.clicked.connect(self._delete_selected)
        bl_row.addWidget(self.keyword_edit, stretch=1)
        bl_row.addWidget(add_btn)
        bl_row.addWidget(del_btn)
        bl_layout.addLayout(bl_row)
        root.addWidget(blacklist_card)

        # ----- 数据 -----
        data_card = QFrame()
        data_card.setObjectName("card")
        data_layout = QVBoxLayout(data_card)
        data_layout.setContentsMargins(18, 14, 18, 14)
        data_title = QLabel("数据")
        data_title.setObjectName("title")
        data_layout.addWidget(data_title)
        data_hint = QLabel("备份为单个数据库文件；CSV 可用 Excel/WPS 打开分析。")
        data_hint.setObjectName("muted2")
        data_layout.addWidget(data_hint)
        data_row = QHBoxLayout()
        backup_btn = QPushButton("备份数据")
        backup_btn.clicked.connect(self.backup_requested.emit)
        restore_btn = QPushButton("从备份恢复…")
        restore_btn.clicked.connect(self.restore_requested.emit)
        export_btn = QPushButton("导出 CSV 报表…")
        export_btn.clicked.connect(self.export_csv_requested.emit)
        clear_btn = QPushButton("清空测试数据…")
        clear_btn.setObjectName("danger")
        clear_btn.setToolTip("按类删除记录（专注/分心、应用使用、金币、任务），用于清除测试数据")
        clear_btn.clicked.connect(self.clear_data_requested.emit)
        data_row.addWidget(backup_btn)
        data_row.addWidget(restore_btn)
        data_row.addWidget(export_btn)
        data_row.addWidget(clear_btn)
        data_row.addStretch(1)
        data_layout.addLayout(data_row)
        root.addWidget(data_card)

        # ----- 保存 -----
        save_row = QHBoxLayout()
        self.save_btn = QPushButton("保存设置")
        self.save_btn.setObjectName("primary")
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(self._on_save)
        data_btn = QPushButton("打开数据文件夹")
        data_btn.clicked.connect(self.open_data_dir.emit)
        save_row.addWidget(self.save_btn)
        save_row.addWidget(data_btn)
        save_row.addStretch(1)
        root.addLayout(save_row)
        from core.version import __version__
        version_label = QLabel(f"自律番茄钟 v{__version__}")
        version_label.setObjectName("muted")
        root.addWidget(version_label)
        root.addStretch(1)

        self.load_settings()

    # ---------- 数据 ----------
    def load_settings(self) -> None:
        s = self._store
        self.work_spin.setValue(s.get_int("work_min", 45))
        self.short_spin.setValue(s.get_int("short_break_min", 5))
        self.long_spin.setValue(s.get_int("long_break_min", 15))
        self.rounds_spin.setValue(s.get_int("rounds_before_long", 4))
        self.goal_spin.setValue(s.get_int("daily_goal", 6))
        self.sound_check.setChecked(s.get_int("sound_enabled", 1) == 1)
        self.auto_break_check.setChecked(s.get_int("auto_start_breaks", 1) == 1)
        self.update_check.setChecked(s.get_int("update_check_enabled", 0) == 1)
        close_index = self.close_combo.findData(s.get_setting("close_action", "ask"))
        self.close_combo.setCurrentIndex(close_index if close_index >= 0 else 0)
        self.blacklist_list.clear()
        for keyword in s.get_blacklist():
            self.blacklist_list.addItem(keyword)
        theme_index = self.theme_combo.findData(s.get_setting("theme", "dark"))
        self.theme_combo.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        self.reminder_check.setChecked(s.get_int("break_reminder_enabled", 0) == 1)
        self.reminder_min_spin.setValue(s.get_int("break_reminder_min", 60))
        self.reminder_text_edit.setText(
            s.get_setting("break_reminder_text", ""))
        try:
            categories = json.loads(s.get_setting("categories", "[]"))
        except json.JSONDecodeError:
            categories = []
        self.categories_edit.setText("、".join(categories))
        # 注册表为准
        from core import autostart
        self.autostart_check.setChecked(autostart.is_enabled())

    def _on_theme_combo(self, index: int) -> None:
        self.theme_changed.emit(self.theme_combo.itemData(index))

    def _add_keyword(self) -> None:
        text = self.keyword_edit.text().strip()
        if text and not self.blacklist_list.findItems(
                text, Qt.MatchExactly):
            self.blacklist_list.addItem(text)
        self.keyword_edit.clear()

    def _delete_selected(self) -> None:
        for item in self.blacklist_list.selectedItems():
            self.blacklist_list.takeItem(self.blacklist_list.row(item))

    def _on_save(self) -> None:
        categories = [c.strip() for c in
                      self.categories_edit.text().replace("，", ",").split(",")
                      if c.strip()]
        payload = {
            "work_min": self.work_spin.value(),
            "short_break_min": self.short_spin.value(),
            "long_break_min": self.long_spin.value(),
            "rounds_before_long": self.rounds_spin.value(),
            "daily_goal": self.goal_spin.value(),
            "sound_enabled": 1 if self.sound_check.isChecked() else 0,
            "auto_start_breaks": 1 if self.auto_break_check.isChecked() else 0,
            "update_check_enabled": 1 if self.update_check.isChecked() else 0,
            "close_action": self.close_combo.currentData(),
            "break_reminder_enabled": 1 if self.reminder_check.isChecked() else 0,
            "break_reminder_min": self.reminder_min_spin.value(),
            "break_reminder_text": self.reminder_text_edit.text().strip(),
            "categories": json.dumps(categories, ensure_ascii=False),
            "blacklist": [self.blacklist_list.item(i).text()
                          for i in range(self.blacklist_list.count())],
        }
        self.settings_saved.emit(payload)
