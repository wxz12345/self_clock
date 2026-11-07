# -*- coding: utf-8 -*-
"""白噪音混音器：多音色叠加、各自音量滑块，实时生效并持久化。"""
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel,
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
        self.setMinimumWidth(400)
        self.setMinimumHeight(560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(10)
        hint = QLabel("可同时叠加多种声音，各自调音量；设置实时保存。")
        hint.setObjectName("muted")
        outer.addWidget(hint)

        # 音色较多，列表区可滚动
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        list_body = QWidget()
        layout = QVBoxLayout(list_body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        scroll.setWidget(list_body)
        outer.addWidget(scroll, stretch=1)

        self._rows = {}
        mix = self._load_mix()
        for name in NOISES:
            if not self.sound.has_noise(name):
                continue  # 音源文件缺失（如未随仓库分发的 NC 音色）则不显示该行
            level = float(mix.get(name, 0.0))
            row = QHBoxLayout()
            checkbox = QCheckBox(NOISE_LABELS.get(name, name))
            checkbox.setChecked(level > 0.001)
            checkbox.toggled.connect(
                lambda on, n=name, s=self: self._on_toggle(n, on))
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(int(level * 100))
            slider.valueChanged.connect(
                lambda v, n=name, s=self: self._on_slider(n, v))
            value_label = QLabel(f"{int(level * 100)}%")
            value_label.setFixedWidth(38)
            value_label.setObjectName("muted")
            row.addWidget(checkbox)
            row.addWidget(slider, stretch=1)
            row.addWidget(value_label)
            layout.addLayout(row)
            self._rows[name] = {"checkbox": checkbox, "slider": slider,
                                "label": value_label, "applying": False}
        layout.addStretch(1)

        buttons = QHBoxLayout()
        stop_all = QPushButton("全部停止")
        stop_all.setObjectName("danger")
        stop_all.clicked.connect(self._stop_all)
        buttons.addWidget(stop_all)
        buttons.addStretch(1)
        close = QPushButton("关闭")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        outer.addLayout(buttons)

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
        mix = {n: round(v, 2) for n, v in self.sound.get_mix().items() if v > 0.001}
        self.store.set_setting("noise_mix", json.dumps(mix, ensure_ascii=False))

    # ---------- 交互 ----------
    def _apply(self, name: str, level: float) -> None:
        row = self._rows[name]
        if row["applying"]:
            return
        row["applying"] = True
        try:
            self.sound.set_noise_level(name, level)
            row["slider"].setValue(int(level * 100))
            row["label"].setText(f"{int(level * 100)}%")
            row["checkbox"].setChecked(level > 0.001)
            self._save_mix()
        finally:
            row["applying"] = False

    def _on_toggle(self, name: str, on: bool) -> None:
        if self._rows[name]["applying"]:
            return
        self._apply(name, self._rows[name]["slider"].value() / 100.0
                    if on else 0.0)

    def _on_slider(self, name: str, value: int) -> None:
        if self._rows[name]["applying"]:
            return
        self._apply(name, value / 100.0)

    def _stop_all(self) -> None:
        self.sound.stop_noise()
        for name, row in self._rows.items():
            row["applying"] = True
            row["slider"].setValue(0)
            row["label"].setText("0%")
            row["checkbox"].setChecked(False)
            row["applying"] = False
        self._save_mix()
