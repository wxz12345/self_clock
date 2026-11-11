# -*- coding: utf-8 -*-
"""提醒事项页：新建/编辑提醒，按"待提醒 / 已完成"分组展示。"""
from datetime import datetime

from PySide6.QtCore import QDateTime, QSize, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from .elided_label import ElidedLabel


class ReminderDialog(QDialog):
    """新建提醒：标题必填，事件时间 + 提前量决定提醒时间。"""

    LEADS = [("准时", 0), ("提前 5 分钟", 5), ("提前 15 分钟", 15),
             ("提前 30 分钟", 30), ("提前 60 分钟", 60)]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建提醒")
        self.setMinimumWidth(420)

        form = QFormLayout(self)
        form.setContentsMargins(24, 22, 24, 20)
        form.setSpacing(12)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("要提醒的事情，如：取快递 / 导师组会")
        form.addRow("事项", self.title_edit)

        self.event_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.event_edit.setCalendarPopup(True)
        self.event_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        form.addRow("事件时间", self.event_edit)

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("可选，如：实验楼 305 / 线上腾讯会议")
        form.addRow("地点", self.location_edit)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("可选备注")
        form.addRow("备注", self.note_edit)

        self.lead_combo = QComboBox()
        for label, _ in self.LEADS:
            self.lead_combo.addItem(label)
        form.addRow("提醒时机", self.lead_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("保存")
        buttons.button(QDialogButtonBox.Ok).setObjectName("primary")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_ok(self) -> None:
        if not self.title_edit.text().strip():
            self.title_edit.setFocus()
            return
        self.accept()

    def values(self) -> dict:
        event = self.event_edit.dateTime().toPython()
        lead_min = self.LEADS[self.lead_combo.currentIndex()][1]
        return {
            "title": self.title_edit.text().strip(),
            "event_ts": event.timestamp(),
            "location": self.location_edit.text().strip(),
            "note": self.note_edit.text().strip(),
            "remind_ts": event.timestamp() - lead_min * 60,
        }


class RemindersView(QWidget):
    create_requested = Signal(dict)
    complete_requested = Signal(int)
    snooze_requested = Signal(int)
    delete_requested = Signal(int)

    ROW_HEIGHT = 58

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        head = QHBoxLayout()
        title = QLabel("提醒事项")
        title.setObjectName("title")
        head.addWidget(title)
        head.addStretch(1)
        add_btn = QPushButton("＋ 新建提醒")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._on_create)
        head.addWidget(add_btn)
        root.addLayout(head)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.NoSelection)
        self.list_widget.setSpacing(4)
        root.addWidget(self.list_widget, stretch=1)

    # ---------- 交互 ----------
    def _on_create(self) -> None:
        dialog = ReminderDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.create_requested.emit(dialog.values())

    # ---------- 渲染 ----------
    def refresh(self, reminders: list) -> None:
        self.list_widget.clear()
        pending = [r for r in reminders if r["status"] != "done"]
        done = [r for r in reminders if r["status"] == "done"]
        if not pending and not done:
            empty = QListWidgetItem("还没有提醒事项。快递、组会、取车……都交给它吧")
            empty.setFlags(Qt.NoItemFlags)
            empty.setTextAlignment(Qt.AlignCenter)
            empty.setSizeHint(QSize(0, 60))
            self.list_widget.addItem(empty)
            return
        if pending:
            self._add_header("📌 待提醒")
            for row in pending:
                self._add_row(row)
        if done:
            self._add_header("☑ 已完成")
            for row in done:
                self._add_row(row)

    def _add_header(self, text: str) -> None:
        # 条目本身不设文字：文字由下面的 QLabel 负责显示。若条目也带同样的文字，
        # 条目绘制的文字会和叠在上面的 QLabel 错位重叠，表现为“重影”。
        item = QListWidgetItem()
        item.setFlags(Qt.NoItemFlags)
        item.setSizeHint(QSize(0, 34))
        self.list_widget.addItem(item)
        label = QLabel(text)
        label.setObjectName("muted")
        self.list_widget.setItemWidget(item, label)

    def _add_row(self, row) -> None:
        item = QListWidgetItem()
        self.list_widget.addItem(item)
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        info = QVBoxLayout()
        info.setSpacing(2)
        title_label = ElidedLabel(row["title"])   # 过长自动省略
        title_label.setStyleSheet("font-weight: bold;")
        info.addWidget(title_label)
        detail_parts = []
        if row["event_ts"]:
            detail_parts.append("📅 " + datetime.fromtimestamp(
                row["event_ts"]).strftime("%m-%d %H:%M"))
        if row["location"]:
            detail_parts.append("📍 " + row["location"])
        status = {"pending": "待提醒", "reminded": "已到点", "done": "已完成"}[
            row["status"]]
        detail_parts.append(status)
        detail = ElidedLabel(" · ".join(detail_parts))
        detail.setObjectName("muted2")
        info.addWidget(detail)
        layout.addLayout(info, stretch=1)

        if row["status"] == "reminded":
            snooze_btn = QPushButton("稍后 5 分钟")
            snooze_btn.clicked.connect(
                lambda _=False, rid=row["id"]: self.snooze_requested.emit(rid))
            snooze_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            layout.addWidget(snooze_btn)
            done_btn = QPushButton("✓ 完成")
            done_btn.setObjectName("primary")
            done_btn.clicked.connect(
                lambda _=False, rid=row["id"]: self.complete_requested.emit(rid))
            done_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            layout.addWidget(done_btn)
        delete_btn = QPushButton("🗑")
        delete_btn.clicked.connect(
            lambda _=False, rid=row["id"]: self.delete_requested.emit(rid))
        delete_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(delete_btn)
        # 行高按内容实际需要的高度算（ROW_HEIGHT 为下限），避免按钮被压扁
        item.setSizeHint(QSize(0, max(self.ROW_HEIGHT,
                                      widget.sizeHint().height() + 8)))
        self.list_widget.setItemWidget(item, widget)
