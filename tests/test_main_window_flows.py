# -*- coding: utf-8 -*-
"""主窗口级别的流程回归（离屏）：顺计时启动显示、迷你窗随屏幕变化、托盘打开主窗口。"""
import os

import pytest
from PySide6.QtCore import QPoint, QRect, QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from app import mini_overlay as mo
from app import theme
from app.main_window import MainWindow
from core.timer import Phase
from core.sound import SoundPlayer
from core.store import Store

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "assets")


def _pump(ms=50):
    t = QTimer()
    t.setSingleShot(True)
    t.start(ms)
    while t.isActive():
        QApplication.processEvents()


@pytest.fixture
def make_window(tmp_path):
    made = []

    def _make(**settings):
        store = Store(str(tmp_path))
        for k, v in settings.items():
            store.set_setting(k, v)
        theme.set_theme("dark")
        w = MainWindow(store, SoundPlayer(ASSETS), str(tmp_path), ASSETS)
        made.append((w, store))
        w.show()
        _pump()
        return w, store

    yield _make
    for w, store in made:
        w._teardown()
        store.close()


# ---------- 顺计时：启动 / 改设置后显示 00:00，而不是 45:00 ----------
def test_stopwatch_mode_startup_shows_zero_not_pomodoro_countdown(make_window):
    w, _ = make_window(timer_mode="stopwatch")
    assert w.stopwatch_mode
    assert w.focus_view.ring._time_text == "00:00"
    assert w.focus_view.ring._progress == 0.0
    assert w.focus_view.phase_label.text() == "准备开始顺计时"
    assert w.focus_view.btn_primary.text() == "开始顺计时"


def test_saving_settings_in_stopwatch_mode_keeps_zero_display(make_window):
    w, _ = make_window(timer_mode="stopwatch")
    w.settings_view._on_save()          # 保存设置会触发一次状态刷新
    _pump()
    assert w.focus_view.ring._time_text == "00:00"
    assert w.focus_view.btn_primary.text() == "开始顺计时"


def test_pomodoro_mode_still_shows_countdown(make_window):
    w, _ = make_window(timer_mode="pomodoro")
    assert w.focus_view.ring._time_text == "45:00"


# ---------- 迷你窗：显示器拔掉后回到主屏 ----------
def test_mini_returns_to_primary_when_its_monitor_disappears(make_window, monkeypatch):
    w, store = make_window()
    main = QRect(0, 0, 1920, 1080)
    right = QRect(1920, 0, 1920, 1080)
    store.set_setting("mini_pos", "2500,300")           # 上次停在外接屏上
    monkeypatch.setattr(MainWindow, "_screen_rects",
                        staticmethod(lambda: ([main, right], main)))
    w._toggle_mini()
    _pump()
    assert w.overlay.isVisible() and w.overlay.pos() == QPoint(2500, 300)

    # 拔掉外接屏：只剩主屏，触发重定位
    monkeypatch.setattr(MainWindow, "_screen_rects",
                        staticmethod(lambda: ([main], main)))
    w._relocate_mini()
    centered = QPoint((1920 - mo.SIZE_W) // 2, (1080 - mo.VISUAL_H) // 2)
    assert w.overlay.pos() == centered
    # 把手与按钮区跟着走，且新位置被记住
    assert w.mini_grip.pos() == centered + mo.GRIP_OFFSET
    assert w.mini_controls.pos() == centered + mo.CONTROLS_OFFSET
    assert store.get_setting("mini_pos") == f"{centered.x()},{centered.y()}"


def test_mini_with_stale_saved_position_opens_on_primary(make_window, monkeypatch):
    w, store = make_window()
    main = QRect(0, 0, 1920, 1080)
    store.set_setting("mini_pos", "-2400,200")          # 记忆位置在已不存在的左侧屏
    monkeypatch.setattr(MainWindow, "_screen_rects",
                        staticmethod(lambda: ([main], main)))
    w._toggle_mini()
    _pump()
    assert main.contains(w.overlay.geometry())


# ---------- 托盘打开主窗口：迷你窗必须收起 ----------
def _open_mini(w):
    if w.overlay is not None and w.overlay.isVisible():
        w._toggle_mini()
        _pump()
    w._toggle_mini()
    _pump()
    assert w.overlay.isVisible()


@pytest.mark.parametrize("how", ["menu", "double_click", "click", "second_instance"])
def test_opening_main_window_from_tray_hides_the_mini(make_window, how):
    w, _ = make_window()
    _open_mini(w)
    if how == "menu":
        w.tray.act_show.trigger()
    elif how == "double_click":
        w.tray._on_activated(QSystemTrayIcon.DoubleClick)
    elif how == "click":
        w.tray._on_activated(QSystemTrayIcon.Trigger)
    else:
        w.showNormal()                                  # 第二实例唤起走的就是这个
    _pump()
    assert w.isVisible()
    assert not w.overlay.isVisible()
    assert not w.mini_grip.isVisible() and not w.mini_controls.isVisible()
    assert w.tray.act_mini.text() == "显示迷你窗"


# ---------- 顺计时圆环：整圈 = “专注时长”设置 ----------
def test_stopwatch_ring_follows_focus_duration_setting(make_window):
    w, store = make_window(timer_mode="stopwatch", work_min=25)
    assert w.timer.durations[Phase.FOCUS] == 25
    w.stopwatch._accumulated = 12.5 * 60          # 已计 12.5 分钟
    w._on_stopwatch_state()
    assert w.focus_view.ring._progress == pytest.approx(0.5)   # 25 分钟一圈 -> 半圈
    assert w.focus_view.ring._time_text == "12:30"


def test_stopwatch_ring_updates_when_setting_changes_and_saturates(make_window):
    w, store = make_window(timer_mode="stopwatch", work_min=25)
    w.stopwatch._accumulated = 12.5 * 60
    w._on_stopwatch_state()
    w.settings_view.work_spin.setValue(50)        # 改成 50 分钟并保存
    w.settings_view._on_save()
    _pump()
    assert w.focus_view.ring._progress == pytest.approx(0.25)  # 同样 12.5 分钟，现在是 1/4 圈
    w.stopwatch._accumulated = 80 * 60            # 超过整圈
    w._on_stopwatch_state()
    assert w.focus_view.ring._progress == 1.0     # 满圈后保持满圈


def test_stopwatch_tick_and_mini_use_the_same_progress(make_window):
    w, store = make_window(timer_mode="stopwatch", work_min=20)
    w._toggle_mini()
    _pump()
    w._on_stopwatch_tick(5 * 60)                  # 20 分钟一圈 -> 1/4
    assert w.focus_view.ring._progress == pytest.approx(0.25)
    assert w.overlay._progress == pytest.approx(0.25)
    assert w.focus_view.tree._grow == pytest.approx(0.25)   # 树的生长进度同步
