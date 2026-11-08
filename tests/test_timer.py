# -*- coding: utf-8 -*-
import time

import pytest
from PySide6.QtCore import QCoreApplication

from core.timer import Phase, PomodoroTimer


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def timer(qapp):
    t = PomodoroTimer()
    t.configure(1, 1, 2, 2, False)
    return t


def test_pause_freezes_remaining(timer):
    timer.start_focus()
    timer.pause()
    r1 = timer.remaining_seconds()
    time.sleep(0.2)
    assert timer.remaining_seconds() == r1
    timer.resume()
    assert timer.running and not timer.paused


def test_long_break_after_configured_rounds(timer):
    finished = []
    timer.phase_finished.connect(lambda a, b, c: finished.append((a, b)))
    for _ in range(2):
        timer.start_focus()
        timer._end_ts = time.time() - 1   # 模拟到点
        timer._on_tick()
    assert finished[0] == (Phase.FOCUS, Phase.SHORT_BREAK)
    assert finished[1] == (Phase.FOCUS, Phase.LONG_BREAK)


def test_abandon_reports_elapsed(timer):
    got = []
    timer.focus_abandoned.connect(got.append)
    timer.start_focus()
    timer._end_ts -= 30     # 相当于已专注 30 秒
    timer.abandon_focus()
    assert got and 0.45 < got[0] < 0.6
    assert not timer.running
