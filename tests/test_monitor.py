# -*- coding: utf-8 -*-
import pytest
from PySide6.QtCore import QCoreApplication

from core import monitor
from core.monitor import FrontendMonitor


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def mon(qapp, monkeypatch):
    m = FrontendMonitor()
    hits, samples = [], []
    m.distraction_detected.connect(hits.append)
    m.foreground_sample.connect(lambda n, t: samples.append((n, t)))
    m._hits, m._samples = hits, samples
    return m


def _fg(monkeypatch, name):
    monkeypatch.setattr(monitor, "get_foreground_process_name", lambda: name)


def test_keyword_substring_match_case_insensitive(mon, monkeypatch):
    mon.set_blacklist(["steam", "  "])       # 空白关键词应被忽略
    _fg(monkeypatch, "Steam.EXE")
    mon._check_once()
    assert mon._hits == ["Steam.EXE"] and len(mon._samples) == 1


def test_same_keyword_deduped_within_window(mon, monkeypatch):
    mon.set_blacklist(["steam"])
    _fg(monkeypatch, "steam.exe")
    mon._check_once()
    mon._check_once()
    assert len(mon._hits) == 1 and len(mon._samples) == 2   # 采样照记，告警只一次


def test_dedup_expires(mon, monkeypatch):
    mon.set_blacklist(["steam"])
    _fg(monkeypatch, "steam.exe")
    mon._check_once()
    mon._last_hit["steam"] -= monitor.DEDUP_WINDOW_SEC + 1
    mon._check_once()
    assert len(mon._hits) == 2


def test_empty_blacklist_samples_only(mon, monkeypatch):
    _fg(monkeypatch, "code.exe")
    mon._check_once()
    assert mon._hits == [] and len(mon._samples) == 1


def test_no_foreground_means_no_sample(mon, monkeypatch):
    _fg(monkeypatch, None)
    mon._check_once()
    assert mon._samples == []
