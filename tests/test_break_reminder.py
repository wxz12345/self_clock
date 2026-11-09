# -*- coding: utf-8 -*-
import pytest
from PySide6.QtCore import QCoreApplication

from core.break_reminder import BreakReminder


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


def test_enable_disable_and_min_interval(qapp):
    br = BreakReminder()
    br.configure(True, 1)                    # 低于下限，按 5 分钟
    assert br.active and br.interval_minutes == 5
    br.configure(False, 60)
    assert not br.active


def test_reconfigure_does_not_duplicate_signal(qapp):
    br = BreakReminder()
    got = []
    br.fired.connect(lambda: got.append(1))
    for _ in range(5):                       # 模拟反复保存设置
        br.configure(True, 30)
    br._timer.timeout.emit()                 # 模拟一次到点
    assert got == [1]                        # 只触发一次，而不是 5 次
