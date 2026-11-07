# -*- coding: utf-8 -*-
"""游戏化计算：金币、树阶段、连续达标天数。纯函数，不依赖 Qt。"""
from datetime import date, timedelta

# 每完成 1 个番茄获得的金币
COINS_PER_POMODORO = 10

# 树阶段：(累计金币下限, 阶段名)
TREE_STAGES = [
    (0, "种子"),
    (50, "幼苗"),
    (150, "小树"),
    (350, "大树"),
]


def tree_stage(coins: int) -> tuple[int, str]:
    """根据累计金币返回 (阶段序号, 阶段名)。"""
    index = 0
    for i, (threshold, _) in enumerate(TREE_STAGES):
        if coins >= threshold:
            index = i
    return index, TREE_STAGES[index][1]


def streak(daily_pomodoros: dict[str, int], goal: int,
           today: date | None = None) -> int:
    """连续达标天数。

    从今天（或昨天，若今天尚未达标）向前数，每天完成番茄数 >= goal 记 1 天。
    今天没达标不打断连击——今天还在进行中。
    """
    today = today or date.today()
    cursor = today
    if daily_pomodoros.get(cursor.isoformat(), 0) < goal:
        cursor -= timedelta(days=1)
    count = 0
    while daily_pomodoros.get(cursor.isoformat(), 0) >= goal:
        count += 1
        cursor -= timedelta(days=1)
    return count
