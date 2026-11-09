# -*- coding: utf-8 -*-
import pytest

from core import update_check
from core.update_check import is_newer, parse_version


@pytest.mark.parametrize("latest,current,expected", [
    ("v2.0.1", "2.0.0", True),
    ("v2.0.0", "2.0.0", False),
    ("v1.9.9", "2.0.0", False),
    ("v2.1", "2.0.9", True),
    ("v2.0.0.1", "2.0.0", True),      # 四段版本号（项目历史上用过 v1.1.4.1）
    ("garbage", "2.0.0", False),
    ("v2.0.0-beta", "2.0.0", False),
])
def test_is_newer(latest, current, expected):
    assert is_newer(latest, current) is expected


def test_parse_version():
    assert parse_version("v1.1.4.1") == (1, 1, 4, 1)
    assert parse_version("") == ()


def test_fetch_latest_swallows_network_errors(monkeypatch):
    def boom(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(update_check.urllib.request, "urlopen", boom)
    assert update_check.fetch_latest() is None
