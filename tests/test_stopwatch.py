# -*- coding: utf-8 -*-
import time

import pytest
from PySide6.QtCore import QCoreApplication

from core.stopwatch import Stopwatch


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


def test_accumulates_across_pause_and_resume(qapp):
    sw = Stopwatch()
    sw.start()
    sw._since -= 30          # 已计 30 秒
    sw.pause()
    frozen = sw.elapsed_seconds()
    time.sleep(0.15)
    assert sw.elapsed_seconds() == frozen      # 暂停期间不增长
    assert 29.9 < frozen < 31
    sw.resume()
    sw._since -= 30
    assert 59.9 < sw.elapsed_seconds() < 61.5


def test_stop_returns_minutes_and_resets(qapp):
    sw = Stopwatch()
    sw.start()
    sw._since -= 90
    minutes = sw.stop()
    assert 1.49 < minutes < 1.55
    assert not sw.running and sw.elapsed_seconds() == 0.0


def test_start_is_idempotent(qapp):
    sw = Stopwatch()
    sw.start()
    sw._since -= 10
    sw.start()               # 运行中重复 start 不应清零
    assert sw.elapsed_seconds() >= 10
