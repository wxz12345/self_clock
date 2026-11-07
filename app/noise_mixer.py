# -*- coding: utf-8 -*-
"""白噪音混音器：＋添加需要的音源，逐个调音量，实时生效并持久化。"""
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QSlider,
                               QVBoxLayout, QWidget)

from core.sound import DEFAULT_VOLUME, NOISES

NOISE_LABELS = {
    "rain": "🌧 雨声·车顶",
    "storm1": "⛈ 雷雨①", "storm2": "⛈ 雷雨②", "storm3": "⛈ 雷雨③",
    "storm4": "⛈ 雷雨④", "storm5": "⛈ 雷雨⑤",
    "pure_thunder": "🌩 纯雷声（NC）",
    "pure_rain1": "🌧 纯雨声①", "pure_rain2": "🌧 纯雨声②",
    "pure_rain3": "🌧 纯雨声③",
    "crickets": "🦗 虫鸣",
    "waves": "🌊 海浪", "fire": "🔥 篝火", "wind": "🍃 风声",
    "birds": "🐦 鸟鸣", "cafe": "☕ 咖啡馆", "brown": "🟤 棕噪音",
}


class NoiseMixerDialog(QDialog):
    def __init__(self, sound, store, parent=None):
        super().__init__(parent)
        self.sound = sound
        self.store = store
        self.setWindowTitle("白噪音混音器")
        self.setMinimumWidth(420)
        self.setMinimumHeight(420)
        self._updating = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(10)
        hint = QLabel("点「＋ 添加音源」把需要的声音加进混音，各自调音量，实时保存。")
        hint.setObjectName("muted")
        outer.addWidget(hint)

        # 已添加音源列表（可滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._list_body = QWidget()
        self._rows_layout = QVBoxLayout(self._list_body)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(8)
        scroll.setWidget(self._list_body)
        outer.addWidget(scroll, stretch=1)

        empty = QLabel("还没有添加音源——从下面选一个开始 🎧")
        empty.setObjectName("muted")
        empty.setAlignment(Qt.AlignCenter)
        self._empty_label = empty
        outer.addWidget(self._empty_label)

        # 添加区：下拉框 + ＋按钮
        add_row = QHBoxLayout()
        self.available_combo = QComboBox()
        add_row.addWidget(self.available_combo, stretch=1)
        self._add_btn = QPushButton("＋ 添加音源")
        self._add_btn.setObjectName("primary")
        self._add_btn.clicked.connect(self._on_add)
        add_row.addWidget(self._add_btn)
        outer.addLayout(add_row)

        buttons = QHBoxLayout()
        stop_all = QPushButton("全部停止")
        stop_all.setObjectName("danger")
        stop_all.clicked.connect(self._on_stop_all)
        buttons.addWidget(stop_all)
        buttons.addStretch(1)
        close = QPushButton("关闭")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        outer.addLayout(buttons)

        self._refresh_rows()
        self._refresh_available()

    # ---------- 数据 ----------
    def _load_mix(self) -> dict:
        raw = self.store.get_setting("noise_mix", "")
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        return {}

    def _save_mix(self) -> None:
        mix = {n: round(v, 2) for n, v in self.sound.get_mix().items()}
        self.store.set_setting("noise_mix", json.dumps(mix, ensure_ascii=False))

    def _added_names(self) -> list[str]:
        """已添加到混音列表的音色（含音量 0 的），按注册表顺序。"""
        mix = self.sound.get_mix()
        return [n for n in NOISES if n in mix]

    def _available_names(self) -> list[str]:
        added = set(self._added_names())
        return [n for n in NOISES
                if n not in added and self.sound.has_noise(n)]

    # ---------- 渲染 ----------
    def _refresh_rows(self) -> None:
        self._updating = True
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows = {}
        added = self._added_names()
        self._empty_label.setVisible(not added)
        for name in added:
            level = float(self.sound.get_mix().get(name, DEFAULT_VOLUME))
            self._rows_layout.addLayout(self._build_row(name, level))
        self._updating = False

    def _build_row(self, name: str, level: float) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel(NOISE_LABELS.get(name, name))
        label.setMinimumWidth(120)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(int(level * 100))
        slider.valueChanged.connect(lambda v, n=name: self._on_slider(n, v))
        value_label = QLabel(f"{int(level * 100)}%")
        value_label.setFixedWidth(38)
        value_label.setObjectName("muted")
        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(30)
        remove_btn.setToolTip("移除该音源")
        remove_btn.clicked.connect(lambda: self._on_remove(name))
        row.addWidget(label)
        row.addWidget(slider, stretch=1)
        row.addWidget(value_label)
        row.addWidget(remove_btn)
        self._rows[name] = {"slider": slider, "label": value_label}
        return row

    def _refresh_available(self) -> None:
        self.available_combo.clear()
        available = self._available_names()
        for name in available:
            self.available_combo.addItem(NOISE_LABELS.get(name, name), name)
        enabled = bool(available)
        self.available_combo.setEnabled(enabled)
        self._add_btn.setEnabled(enabled)

    # ---------- 交互 ----------
    def _apply_level(self, name: str, level: float) -> None:
        if self._updating:
            return
        self.sound.set_noise_level(name, level)
        self._save_mix()

    def _on_slider(self, name: str, value: int) -> None:
        self._apply_level(name, value / 100.0)
        if name in self._rows:
            self._rows[name]["label"].setText(f"{value}%")

    def _on_remove(self, name: str) -> None:
        self.sound.remove_noise(name)
        self._save_mix()
        self._refresh_rows()
        self._refresh_available()

    def _on_add(self) -> None:
        name = self.available_combo.currentData()
        if not name:
            return
        self.sound.set_noise_level(name, DEFAULT_VOLUME)
        self._save_mix()
        self._refresh_rows()
        self._refresh_available()

    def _on_stop_all(self) -> None:
        self.sound.stop_noise()
        self._save_mix()
        self._refresh_rows()
        self._refresh_available()
