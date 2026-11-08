# -*- coding: utf-8 -*-
from datetime import date

from core import gamify


def test_tree_stage_thresholds():
    assert gamify.tree_stage(0)[1] == "种子"
    assert gamify.tree_stage(49)[1] == "种子"
    assert gamify.tree_stage(50)[1] == "幼苗"
    assert gamify.tree_stage(10_000)[1] == "大树"


def test_streak_today_not_yet_reached_keeps_chain():
    today = date(2026, 5, 10)
    daily = {"2026-05-09": 6, "2026-05-08": 6, "2026-05-10": 2}
    assert gamify.streak(daily, 6, today) == 2


def test_streak_broken_by_gap():
    today = date(2026, 5, 10)
    daily = {"2026-05-10": 6, "2026-05-08": 6}
    assert gamify.streak(daily, 6, today) == 1
