# -*- coding: utf-8 -*-
"""音效播放。

- 一次性提示音（bell/chime/coin/reminder）：QSoundEffect 加载 wav
- 白噪音混音器（assets/noise/）：每个音色独立的 QMediaPlayer + QAudioOutput，
  可多轨叠加、各自调音量、真正暂停/恢复，无限循环
"""
import os

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import (QAudioOutput, QMediaPlayer, QSoundEffect)

SOUNDS = ("bell", "chime", "coin", "reminder")
# 白噪音注册表：键对应 assets/noise/<键>.mp3，顺序即混音器显示顺序
NOISES = (
    "rain", "pure_rain1", "pure_rain2", "pure_rain3",
    "storm1", "storm2", "storm3", "storm4", "storm5", "pure_thunder",
    "waves", "fire", "wind", "birds", "cafe", "crickets", "brown",
)
DEFAULT_VOLUME = 0.45


class SoundPlayer(QObject):
    """提示音 + 白噪音混音器，统一受 enabled 开关控制。"""

    def __init__(self, assets_dir: str):
        super().__init__()
        self.enabled = True
        self._effects = {}
        for name in SOUNDS:
            effect = QSoundEffect(self)
            path = os.path.join(assets_dir, f"{name}.wav")
            if os.path.exists(path):
                effect.setSource(QUrl.fromLocalFile(path))
            effect.setVolume(0.6)
            self._effects[name] = effect

        # ---- 白噪音混音器 ----
        self._noise_dir = os.path.join(assets_dir, "noise")
        self._tracks = {}   # name -> {"player": QMediaPlayer, "output": QAudioOutput}
        self._levels = {}   # name -> 当前音量（>0 表示在播）

    def _track(self, name: str):
        """惰性创建某音色的播放器。"""
        if name not in self._tracks:
            output = QAudioOutput()
            player = QMediaPlayer()
            player.setAudioOutput(output)
            player.setLoops(QMediaPlayer.Loops.Infinite.value)
            self._tracks[name] = {"player": player, "output": output}
        return self._tracks[name]

    def _source_path(self, name: str) -> str | None:
        for ext in (".mp3", ".wav"):
            candidate = os.path.join(self._noise_dir, f"{name}{ext}")
            if os.path.exists(candidate):
                return candidate
        return None

    # ---------- 提示音 ----------
    def play(self, name: str) -> None:
        if not self.enabled:
            return
        effect = self._effects.get(name)
        if effect and effect.source().isValid():
            effect.play()

    # ---------- 白噪音混音 ----------
    def set_noise_level(self, name: str, level: float) -> None:
        """level 0~1；<=0 表示停掉该音色。"""
        if name not in NOISES:
            return
        level = max(0.0, min(1.0, level))
        if level <= 0.001:
            track = self._tracks.get(name)
            if track:
                track["player"].stop()
            self._levels.pop(name, None)
            return
        track = self._track(name)
        was_playing = self._levels.get(name, 0.0) > 0
        track["output"].setVolume(level)
        self._levels[name] = level
        if not was_playing:
            path = self._source_path(name)
            if path is None:
                self._levels.pop(name, None)
                return
            track["player"].setSource(QUrl.fromLocalFile(path))
            track["player"].play()

    def apply_mix(self, mix: dict) -> None:
        """应用整套混音配置（不破坏正在播放的音色）。"""
        for name in NOISES:
            self.set_noise_level(name, float(mix.get(name, 0.0)))

    def get_mix(self) -> dict:
        return dict(self._levels)

    def active_noises(self) -> list[str]:
        return [n for n, v in self._levels.items() if v > 0.001]

    def stop_noise(self) -> None:
        """停掉全部音色（不清空配置）。"""
        for name in list(self._levels):
            self.set_noise_level(name, 0.0)

    def pause_noise(self) -> None:
        for name in list(self._levels):
            self._tracks[name]["player"].pause()

    def resume_noise(self) -> None:
        for name in list(self._levels):
            self._tracks[name]["player"].play()
