# -*- coding: utf-8 -*-
"""任务/提醒列表的显示回归：按钮不被压扁、分组标题不重影、长文字省略不撑宽。"""
import time

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from app import theme
from app.elided_label import ElidedLabel
from app.reminders_view import RemindersView
from app.tasks_view import TasksView


@pytest.fixture(autouse=True)
def styled_app():
    # 按钮高度来自 QSS 的内边距，必须套上真实样式表才有意义
    app = QApplication.instance()
    theme.set_theme("dark")
    app.setStyleSheet(theme.build_qss())
    yield
    app.setStyleSheet("")


def _tasks(n=4, current=1):
    rows = [{"id": i, "name": f"任务{i}", "estimated": 2, "completed": 0,
             "done": 1 if i == 3 else 0} for i in range(1, n + 1)]
    return rows, current


def test_task_buttons_are_not_squashed():
    view = TasksView()
    rows, cur = _tasks()
    view.refresh(rows, cur)
    view.resize(800, 500)
    view.show()
    QApplication.processEvents()
    buttons = 0
    for i in range(view.list_widget.count()):
        w = view.list_widget.itemWidget(view.list_widget.item(i))
        for b in w.findChildren(QPushButton):
            buttons += 1
            assert b.height() >= b.sizeHint().height(), (
                f"按钮 {b.text()!r} 被压扁：{b.height()} < {b.sizeHint().height()}")
    assert buttons >= 8   # 每行 2 个按钮（设为当前/★当前 + 删除）


def test_reminder_buttons_are_not_squashed():
    view = RemindersView()
    now = time.time()
    view.refresh([
        {"id": 1, "title": "a", "event_ts": now, "location": "x", "note": "",
         "remind_ts": now, "status": "reminded"},
        {"id": 2, "title": "b", "event_ts": now, "location": "", "note": "",
         "remind_ts": now, "status": "pending"},
    ])
    view.resize(800, 500)
    view.show()
    QApplication.processEvents()
    for i in range(view.list_widget.count()):
        w = view.list_widget.itemWidget(view.list_widget.item(i))
        for b in (w.findChildren(QPushButton) if w else []):
            assert b.height() >= b.sizeHint().height()


def test_group_headers_have_no_item_text_to_avoid_ghosting():
    view = RemindersView()
    now = time.time()
    view.refresh([
        {"id": 1, "title": "a", "event_ts": now, "location": "", "note": "",
         "remind_ts": now, "status": "pending"},
        {"id": 2, "title": "b", "event_ts": now, "location": "", "note": "",
         "remind_ts": now, "status": "done"},
    ])
    headers = [view.list_widget.item(i) for i in range(view.list_widget.count())
               if view.list_widget.itemWidget(view.list_widget.item(i)) is not None
               and not view.list_widget.itemWidget(view.list_widget.item(i)).layout()]
    assert len(headers) == 2
    # 条目自身带文字，会和叠在上面的 QLabel 错位重叠成“重影”
    assert all(h.text() == "" for h in headers)
    labels = [view.list_widget.itemWidget(h).text() for h in headers]
    assert any("待提醒" in t for t in labels) and any("已完成" in t for t in labels)


def test_elided_label_shrinks_and_shows_full_text_in_tooltip():
    label = ElidedLabel("很长的一段任务名" * 20)
    assert label.minimumSizeHint().width() == 0      # 不会因文字长度撑宽布局
    label.resize(120, 24)
    label.show()
    QApplication.processEvents()
    assert label.text().endswith("…") and len(label.text()) < len(label.full_text())
    assert label.toolTip() == label.full_text()


def test_elided_label_short_text_untouched():
    label = ElidedLabel("短")
    label.resize(200, 24)
    label.show()
    QApplication.processEvents()
    assert label.text() == "短" and label.toolTip() == ""
