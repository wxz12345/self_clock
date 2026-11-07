# -*- coding: utf-8 -*-
"""番茄钟状态机：只管时间与阶段，不碰数据库、不碰 UI（Flowkeeper 式解耦）。

计时基于"结束时间戳 - 当前时间"，暂停时冻结剩余秒数，
休眠唤醒后也能立刻得到正确的剩余时间。
"""
import time
from enum import Enum

from PySide6.QtCore import QObject, QTimer, Signal


class Phase(Enum):
    FOCUS = "focus"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"

    @property
    def is_break(self) -> bool:
        return self != Phase.FOCUS


class PomodoroTimer(QObject):
    tick = Signal(float, float)          # (剩余秒, 进度 0~1)
    state_changed = Signal()             # running/paused/idle 变化（刷新按钮）
    phase_finished = Signal(object, object, bool)  # (结束的Phase, 下一Phase, 是否已自动开始)
    focus_abandoned = Signal(float)      # 本次实际专注的分钟数

    def __init__(self):
        super().__init__()
        self.durations = {Phase.FOCUS: 45.0,
                          Phase.SHORT_BREAK: 5.0,
                          Phase.LONG_BREAK: 15.0}
        self.rounds_before_long = 4
        self.auto_start_breaks = True

        self._phase = Phase.FOCUS
        self._round = 0            # 当前长休周期内已完成的番茄数
        self._running = False
        self._paused = False
        self._end_ts = 0.0         # running 时的结束时间戳
        self._remaining = 0.0      # paused 时冻结的剩余秒
        self._planned_sec = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._on_tick)

    # ---------- 状态 ----------
    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def running(self) -> bool:
        return self._running

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def completed_in_cycle(self) -> int:
        return self._round

    def remaining_seconds(self) -> float:
        if self._running:
            return max(0.0, self._end_ts - time.time())
        return self._remaining

    def configure(self, work_min: float, short_min: float, long_min: float,
                  rounds: int, auto_start_breaks: bool) -> None:
        self.durations = {Phase.FOCUS: float(work_min),
                          Phase.SHORT_BREAK: float(short_min),
                          Phase.LONG_BREAK: float(long_min)}
        self.rounds_before_long = max(1, int(rounds))
        self.auto_start_breaks = auto_start_breaks

    # ---------- 控制 ----------
    def start_focus(self) -> None:
        self._start(Phase.FOCUS)

    def start_break(self) -> None:
        self._start(self._phase if self._phase.is_break else Phase.SHORT_BREAK)

    def _start(self, phase: Phase) -> None:
        self._phase = phase
        self._planned_sec = self.durations[phase] * 60
        self._end_ts = time.time() + self._planned_sec
        self._running = True
        self._paused = False
        self._timer.start()
        self.state_changed.emit()
        self.tick.emit(self._planned_sec, 0.0)

    def pause(self) -> None:
        if not self._running or self._paused:
            return
        self._remaining = max(0.0, self._end_ts - time.time())
        self._paused = True
        self._timer.stop()
        self.state_changed.emit()

    def resume(self) -> None:
        if not self._running or not self._paused:
            return
        self._end_ts = time.time() + self._remaining
        self._paused = False
        self._timer.start()
        self.state_changed.emit()

    def abandon_focus(self) -> None:
        """放弃当前专注（温和模式：允许，但由 UI 负责先弹原因弹窗）。"""
        if self._phase != Phase.FOCUS or not self._running:
            return
        elapsed_min = (self._planned_sec - self.remaining_seconds()) / 60.0
        self._stop_all()
        self.focus_abandoned.emit(max(0.0, elapsed_min))

    def skip_break(self) -> None:
        """跳过休息，直接进入待专注状态。"""
        if self._phase.is_break and self._running:
            self._stop_all()
            self._phase = Phase.FOCUS

    def dismiss_break(self) -> None:
        """未开始的休息直接跳过（待休息状态）。"""
        if self._phase.is_break and not self._running:
            self._phase = Phase.FOCUS
            self.state_changed.emit()

    def _stop_all(self) -> None:
        self._timer.stop()
        self._running = False
        self._paused = False
        self._remaining = 0.0
        self.state_changed.emit()

    # ---------- 内部 ----------
    def _on_tick(self) -> None:
        remaining = max(0.0, self._end_ts - time.time())
        progress = (1 - remaining / self._planned_sec) if self._planned_sec else 0.0
        self.tick.emit(remaining, progress)
        if remaining <= 0:
            self._complete()

    def _complete(self) -> None:
        finished = self._phase
        if finished == Phase.FOCUS:
            self._round += 1
            nxt = (Phase.LONG_BREAK
                   if self._round % self.rounds_before_long == 0
                   else Phase.SHORT_BREAK)
        else:
            nxt = Phase.FOCUS
        self._stop_all()
        self._phase = nxt
        auto_started = False
        # 休息按设置自动开始；专注永远等用户手动开始（开始的动作本身就是自控仪式）
        if nxt.is_break and self.auto_start_breaks:
            self._start(nxt)
            auto_started = True
        self.phase_finished.emit(finished, nxt, auto_started)
