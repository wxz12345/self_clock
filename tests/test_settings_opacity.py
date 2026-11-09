# -*- coding: utf-8 -*-
"""设置页的迷你窗透明度滑块：读取、实时发信号、外部同步不回环、滚轮不改值。"""
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from app.settings_view import MINI_OPACITY_RANGE, SettingsView
from core.store import Store


@pytest.fixture
def view(tmp_path):
    store = Store(str(tmp_path))
    store.set_setting("mini_opacity", 70)
    v = SettingsView(store, str(tmp_path))
    yield v
    store.close()


def test_loads_saved_value(view):
    assert view.mini_opacity_slider.value() == 70
    assert view.mini_opacity_value.text() == "70%"


def test_slider_emits_live_and_updates_label(view):
    got = []
    view.mini_opacity_changed.connect(got.append)
    view.mini_opacity_slider.setValue(55)
    assert got == [55] and view.mini_opacity_value.text() == "55%"


def test_external_sync_does_not_echo(view):
    got = []
    view.mini_opacity_changed.connect(got.append)
    view.set_mini_opacity(85)                 # 例如来自迷你窗右键菜单
    assert got == []
    assert view.mini_opacity_slider.value() == 85
    assert view.mini_opacity_value.text() == "85%"


def test_value_is_clamped_to_range(view):
    lo, hi = MINI_OPACITY_RANGE
    view.set_mini_opacity(5)
    assert view.mini_opacity_slider.value() == lo
    view.set_mini_opacity(500)
    assert view.mini_opacity_slider.value() == hi


def test_wheel_does_not_change_value(view):
    before = view.mini_opacity_slider.value()
    ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120),
                     Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(view.mini_opacity_slider, ev)
    assert view.mini_opacity_slider.value() == before
