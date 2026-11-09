# -*- coding: utf-8 -*-
import pytest

from core.usage_tracker import UsageTracker


class FakeStore:
    def __init__(self):
        self.rows = []

    def add_app_usage(self, session_id, name, seconds):
        self.rows.append((session_id, name, round(seconds, 3)))

    def totals(self):
        out = {}
        for _, n, s in self.rows:
            out[n] = out.get(n, 0) + s
        return {k: round(v, 3) for k, v in out.items()}


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def env():
    store, clock = FakeStore(), Clock()
    return store, clock, UsageTracker(store, clock)


def test_samples_credit_previous_process(env):
    store, clock, tr = env
    tr.begin(1)
    tr.on_sample(1, "code.exe", 1005)     # 开头 5s 归给首个采样的进程
    tr.on_sample(1, "chrome.exe", 1015)   # 10s 归给 code
    tr.on_sample(1, "chrome.exe", 1020)   # 5s 归给 chrome
    clock.t = 1020
    tr.end(1)
    assert store.totals() == {"code.exe": 15, "chrome.exe": 5}


def test_flush_is_incremental_no_double_count(env):
    store, clock, tr = env
    tr.begin(1)
    tr.on_sample(1, "code.exe", 1010)
    clock.t = 1030
    tr.flush(1, 0.05)                     # 补上 1010→1030 的 20s
    clock.t = 1040
    tr.flush(1, 0.05)                     # 再 10s
    tr.end(1)
    assert store.totals() == {"code.exe": 40}


def test_late_queued_sample_not_counted_twice(env):
    store, clock, tr = env
    tr.begin(1)
    tr.on_sample(1, "a.exe", 1010)
    clock.t = 1030
    tr.flush(1)                           # 已结算到 1030
    tr.on_sample(1, "b.exe", 1020)        # 迟到的旧采样：只换名字，不再计时
    clock.t = 1040
    tr.end(1)
    assert store.totals() == {"a.exe": 30, "b.exe": 10}


def test_ignores_samples_for_other_or_no_session(env):
    store, clock, tr = env
    tr.begin(1)
    tr.on_sample(2, "x.exe", 1010)        # 当前会话不是被跟踪的那个
    tr.on_sample(None, "x.exe", 1020)
    clock.t = 1030
    tr.end(1)
    assert store.rows == []
    assert not tr.is_tracking(1)          # end 后不再跟踪


def test_min_seconds_threshold(env):
    store, clock, tr = env
    tr.begin(1)
    tr.on_sample(1, "tiny.exe", 1000.3)
    clock.t = 1000.3
    tr.flush(1, min_seconds=0.5)
    assert store.rows == []               # 不足门槛不落库
    tr.end(1, min_seconds=0.05)
    assert store.totals() == {"tiny.exe": 0.3}   # 收尾门槛放低后零头也保留
