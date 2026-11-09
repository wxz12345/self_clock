# -*- coding: utf-8 -*-
"""托盘菜单的主题切换项：文字随当前主题变化；设置页下拉框外部同步不回环。"""
import pytest

from app.settings_view import SettingsView
from app.tray import TrayController
from core.store import Store


@pytest.fixture
def tray():
    t = TrayController()
    yield t
    t.hide()


def test_menu_contains_theme_action_between_mini_and_quit(tray):
    actions = [a for a in tray.menu.actions() if not a.isSeparator()]
    texts = [a.text() for a in actions]
    assert texts.index(tray.act_theme.text()) == texts.index(tray.act_mini.text()) + 1
    assert tray.act_quit in actions


def test_label_names_the_target_theme(tray):
    tray.set_theme_label("dark")
    assert tray.act_theme.text() == "切换为浅色主题"
    tray.set_theme_label("light")
    assert tray.act_theme.text() == "切换为深色主题"


def test_settings_theme_combo_syncs_without_echo(tmp_path):
    store = Store(str(tmp_path))
    view = SettingsView(store, str(tmp_path))
    got = []
    view.theme_changed.connect(got.append)
    view.set_theme("light")
    assert view.theme_combo.currentData() == "light"
    assert got == []                       # 外部同步不应再触发一次切换
    view.set_theme("nonexistent")          # 未知主题名：忽略
    assert view.theme_combo.currentData() == "light"
    store.close()
