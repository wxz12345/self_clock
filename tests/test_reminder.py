# -*- coding: utf-8 -*-
import time

import pytest
from PySide6.QtCore import QCoreApplication

from core.reminder import MISSED_GRACE_SEC, ReminderScheduler
from core.store import Store


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path))
    yield s
    s.close()


def test_due_emitted_once_and_marked(qapp, store):
    now = time.time()
    store.add_reminder("开会", now + 3600, "会议室", "", now - 5)
    store.add_reminder("未来的事", now + 7200, "", "", now + 3600)
    got = []
    sched = ReminderScheduler(store)     # 构造即补扫一次
    sched.due.connect(got.append)
    sched.check()                        # 再扫一次不应重复发
    assert [r["title"] for r in store.conn.execute(
        "SELECT title FROM reminders WHERE status='reminded'")] == ["开会"]
    assert got == []                     # 构造时那次已发过，之后不重复


def test_missed_flag(qapp, store):
    now = time.time()
    store.add_reminder("很久以前", None, "", "", now - MISSED_GRACE_SEC - 120)
    store.add_reminder("刚到点", None, "", "", now - 3)
    got = []
    sched = ReminderScheduler.__new__(ReminderScheduler)
    from PySide6.QtCore import QObject
    QObject.__init__(sched)
    sched._store = store
    sched.due.connect(got.append)
    sched.check()
    by_title = {r["title"]: r["missed"] for r in got}
    assert by_title == {"很久以前": True, "刚到点": False}


def test_snooze_makes_it_due_again(qapp, store):
    now = time.time()
    store.add_reminder("喝水", None, "", "", now - 1)
    rid = store.due_reminders()[0]["id"]
    store.mark_reminder_reminded(rid)
    assert store.due_reminders() == []
    store.snooze_reminder(rid, seconds=-1)   # 立刻到期
    assert [r["id"] for r in store.due_reminders()] == [rid]
