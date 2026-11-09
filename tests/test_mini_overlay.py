# -*- coding: utf-8 -*-
"""迷你窗几何与按钮显隐（离屏）。"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import mini_overlay as mo  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_compact_size():
    # 回归保护：迷你窗曾是 230×212，现为单行紧凑条
    assert mo.SIZE_W <= 260 and mo.VISUAL_H <= 56


def test_parts_fit_inside_the_pill():
    # 把手与按钮区都在药丸范围内，且互不重叠
    assert mo.GRIP_OFFSET.x() >= 0 and mo.GRIP_OFFSET.x() + mo.GRIP_W <= mo.SIZE_W
    assert mo.CONTROLS_OFFSET.x() + mo.CONTROLS_W <= mo.SIZE_W
    assert mo.GRIP_OFFSET.x() + mo.GRIP_W <= mo.CONTROLS_OFFSET.x()
    assert mo.TEXT_X < mo.CONTROLS_OFFSET.x()


def test_window_sizes(qapp):
    assert (mo.MiniOverlay().width(), mo.MiniOverlay().height()) == (mo.SIZE_W, mo.VISUAL_H)
    grip, ctl = mo.MiniGrip(), mo.MiniControls()
    assert (grip.width(), grip.height()) == (mo.GRIP_W, mo.VISUAL_H)
    assert (ctl.width(), ctl.height()) == (mo.CONTROLS_W, mo.VISUAL_H)


def test_controls_actions_and_icons(qapp):
    ctl = mo.MiniControls()
    ctl.show()
    ctl.set_actions("暂停", True, True, False)
    assert ctl.btn_primary.kind == "pause" and ctl.btn_primary.toolTip() == "暂停"
    assert ctl.btn_abandon.isVisible() and not ctl.btn_skip.isVisible()
    ctl.set_actions("开始休息", True, False, True)
    assert ctl.btn_primary.kind == "play"
    assert not ctl.btn_abandon.isVisible() and ctl.btn_skip.isVisible()
    assert ctl.btn_expand.isVisible()                 # 返回按钮始终可见


def test_buttons_emit_signals(qapp):
    ctl = mo.MiniControls()
    got = []
    ctl.primary_requested.connect(lambda: got.append("p"))
    ctl.abandon_requested.connect(lambda: got.append("a"))
    ctl.skip_requested.connect(lambda: got.append("s"))
    ctl.expand_requested.connect(lambda: got.append("e"))
    for b in (ctl.btn_primary, ctl.btn_abandon, ctl.btn_skip, ctl.btn_expand):
        b.click()
    assert got == ["p", "a", "s", "e"]


def test_state_label_strips_leading_symbol(qapp):
    ov = mo.MiniOverlay()
    ov.set_state_label("⏱ 顺计时中")
    assert ov._state_text == "顺计时中"


def test_long_time_text_shrinks_to_fit(qapp):
    from PySide6.QtGui import QPixmap
    ov = mo.MiniOverlay()
    ov.set_display("12:34:56", 0.5, "focus")
    ov.render(QPixmap(mo.SIZE_W, mo.VISUAL_H))        # 不应抛异常
