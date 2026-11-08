# -*- coding: utf-8 -*-
import sqlite3
import time
from datetime import date, timedelta

import pytest

from core.backup import auto_backup
from core.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "data"))
    yield s
    try:
        s.close()
    except sqlite3.ProgrammingError:
        pass


def _ts(day: date, hour: int = 12) -> float:
    return time.mktime(day.replace().timetuple()) + hour * 3600


def _usage(store, day: date, process: str, seconds: float):
    store.conn.execute(
        "INSERT INTO app_usage(session_id, ts, process, seconds) VALUES(1,?,?,?)",
        (_ts(day), process, seconds))
    store.conn.commit()


def test_wal_and_indexes(store):
    assert store.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    names = {r[1] for r in store.conn.execute(
        "SELECT * FROM sqlite_master WHERE type='index'")}
    assert {"idx_sessions_start", "idx_distractions_ts",
            "idx_app_usage_ts"} <= names


def test_compact_merges_past_days_only_and_is_idempotent(store):
    today = date.today()
    y = today - timedelta(days=1)
    _usage(store, y, "code.exe", 600)
    _usage(store, y, "code.exe", 300)
    _usage(store, y, "chrome.exe", 120)
    _usage(store, today, "code.exe", 60)
    assert store.compact_app_usage() == 3
    assert store.compact_app_usage() == 0          # 幂等
    daily = {(r["day"], r["process"]): r["seconds"] for r in
             store.conn.execute("SELECT * FROM app_usage_daily")}
    assert daily == {(y.isoformat(), "code.exe"): 900,
                     (y.isoformat(), "chrome.exe"): 120}
    # 今天的明细保留
    assert store.conn.execute("SELECT COUNT(*) FROM app_usage").fetchone()[0] == 1


def test_top_app_usage_spans_detail_and_daily_and_single_day(store):
    today = date.today()
    y = today - timedelta(days=1)
    _usage(store, y, "code.exe", 600)
    store.compact_app_usage()
    _usage(store, today, "code.exe", 60)
    total = {r["process"]: r["s"] for r in store.top_app_usage(30, 8)}
    assert total == {"code.exe": 660}
    only_y = {r["process"]: r["s"] for r in
              store.top_app_usage(30, 8, day=y.isoformat())}
    assert only_y == {"code.exe": 600}
    only_today = {r["process"]: r["s"] for r in
                  store.top_app_usage(30, 8, day=today.isoformat())}
    assert only_today == {"code.exe": 60}


def test_category_and_distraction_by_day(store):
    today = date.today()
    y = today - timedelta(days=1)
    for d, cat, m in ((y, "科研", 40), (today, "课程", 25)):
        sid = store.start_session(None, "focus", 45, cat)
        store.conn.execute(
            "UPDATE sessions SET start_ts=?, actual_min=?, status='completed'"
            " WHERE id=?", (_ts(d), m, sid))
        store.conn.execute(
            "INSERT INTO distractions(session_id, ts, reason) VALUES(?,?,?)",
            (sid, _ts(d), f"{cat}-分心"))
    store.conn.commit()
    assert {r["cat"]: r["m"] for r in
            store.category_minutes(30, day=y.isoformat())} == {"科研": 40}
    assert {r["cat"] for r in store.category_minutes(30)} == {"科研", "课程"}
    assert [r["reason"] for r in
            store.distraction_reason_counts(30, day=today.isoformat())] == ["课程-分心"]


def test_clear_records_clears_daily_table(store):
    _usage(store, date.today() - timedelta(days=2), "a.exe", 10)
    store.compact_app_usage()
    store.clear_records()
    assert store.conn.execute(
        "SELECT COUNT(*) FROM app_usage_daily").fetchone()[0] == 0


def test_backup_api_includes_uncheckpointed_wal_data(store, tmp_path):
    store.set_setting("marker", "hello")
    out = tmp_path / "b.db"
    store.backup_to(str(out))
    b = sqlite3.connect(out)
    assert b.execute(
        "SELECT value FROM settings WHERE key='marker'").fetchone()[0] == "hello"
    b.close()
    auto = auto_backup(store.db_path, str(tmp_path / "bk"))
    assert auto and sqlite3.connect(auto).execute(
        "SELECT value FROM settings WHERE key='marker'").fetchone()[0] == "hello"


def test_merge_from_imports_daily_usage(store, tmp_path):
    other = Store(str(tmp_path / "other"))
    d = date.today() - timedelta(days=3)
    other.conn.execute(
        "INSERT INTO app_usage_daily VALUES(?,?,?)", (d.isoformat(), "x.exe", 50))
    other.conn.commit()
    other.close()
    stats = store.merge_from(str(tmp_path / "other" / "selfclock.db"))
    assert stats["app_usage"] == 1
    assert store.merge_from(str(tmp_path / "other" / "selfclock.db"))["app_usage"] == 0
