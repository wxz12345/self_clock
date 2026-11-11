# -*- coding: utf-8 -*-
"""迷你窗在显示器插拔后的位置校正（纯函数）。"""
from PySide6.QtCore import QPoint, QRect, QSize

from app.mini_overlay import SIZE_W, VISUAL_H, fit_to_screens

SIZE = QSize(SIZE_W, VISUAL_H)
MAIN = QRect(0, 0, 1920, 1080)
RIGHT = QRect(1920, 0, 1920, 1080)          # 主屏右侧的外接屏
LEFT = QRect(-1920, 0, 1920, 1080)          # 主屏左侧的外接屏（负坐标）


def primary_center():
    return QPoint((MAIN.width() - SIZE_W) // 2, (MAIN.height() - VISUAL_H) // 2)


def test_position_on_existing_screen_is_unchanged():
    assert fit_to_screens(QPoint(300, 200), SIZE, [MAIN, RIGHT], MAIN) == QPoint(300, 200)


def test_window_on_unplugged_external_monitor_returns_to_primary():
    # 外接屏拔掉后，只剩主屏；原来在右侧屏幕上的窗口回到主屏正中
    assert fit_to_screens(QPoint(2500, 300), SIZE, [MAIN], MAIN) == primary_center()


def test_window_on_unplugged_left_monitor_with_negative_coords():
    assert fit_to_screens(QPoint(-1500, 400), SIZE, [MAIN], MAIN) == primary_center()


def test_window_still_on_second_monitor_stays_when_it_is_connected():
    assert fit_to_screens(QPoint(2500, 300), SIZE, [MAIN, RIGHT], MAIN) == QPoint(2500, 300)
    assert fit_to_screens(QPoint(-1500, 400), SIZE, [MAIN, LEFT], MAIN) == QPoint(-1500, 400)


def test_partially_off_screen_is_clamped_inside_its_screen():
    # 中心还在主屏内，但右边缘伸出屏幕 -> 收拢到屏幕内
    p = fit_to_screens(QPoint(1750, 1050), SIZE, [MAIN], MAIN)
    assert p == QPoint(MAIN.right() - SIZE_W + 1, MAIN.bottom() - VISUAL_H + 1)
    assert QRect(p, SIZE).intersected(MAIN) == QRect(p, SIZE)


def test_resolution_shrink_pulls_window_back():
    small = QRect(0, 0, 1280, 720)
    p = fit_to_screens(QPoint(1700, 900), SIZE, [small], small)   # 原先在 1920x1080 里的位置
    assert p == QPoint((small.width() - SIZE_W) // 2, (small.height() - VISUAL_H) // 2)


def test_no_screen_info_leaves_position_untouched():
    assert fit_to_screens(QPoint(123, 456), SIZE, [], MAIN) == QPoint(123, 456)
