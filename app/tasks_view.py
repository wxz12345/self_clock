# -*- coding: utf-8 -*-
"""任务列表页：增删勾选任务、预估番茄数、设为当前任务。"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)


class TasksView(QWidget):
    add_task = Signal(str, int)
    toggle_task = Signal(int, bool)
    delete_task = Signal(int)
    set_current_task = Signal(object)  # task_id 或 None

    ROW_HEIGHT = 46

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_task_id = None
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title = QLabel("任务")
        title.setObjectName("title")
        root.addWidget(title)

        add_row = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("新任务，比如：复习高数第三章")
        self.name_edit.returnPressed.connect(self._on_add)
        self.est_spin = QSpinBox()
        self.est_spin.setRange(1, 30)
        self.est_spin.setValue(2)
        self.est_spin.setSuffix(" 个番茄")
        add_btn = QPushButton("添加")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._on_add)
        add_row.addWidget(self.name_edit, stretch=1)
        add_row.addWidget(self.est_spin)
        add_row.addWidget(add_btn)
        root.addLayout(add_row)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.NoSelection)
        self.list_widget.setSpacing(4)
        root.addWidget(self.list_widget, stretch=1)

        hint = QLabel("💡 点击任务名设为当前任务；在专注页也可切换")
        hint.setObjectName("muted2")
        root.addWidget(hint)

    # ---------- 交互 ----------
    def _on_add(self) -> None:
        name = self.name_edit.text().strip()
        if name:
            self.add_task.emit(name, self.est_spin.value())
            self.name_edit.clear()

    # ---------- 渲染 ----------
    def refresh(self, tasks: list, current_task_id) -> None:
        self._current_task_id = current_task_id
        self.list_widget.clear()
        if not tasks:
            empty = QListWidgetItem("还没有任务，先添加一个吧")
            empty.setFlags(Qt.NoItemFlags)
            empty.setTextAlignment(Qt.AlignCenter)
            empty.setSizeHint(QSize(0, 60))
            self.list_widget.addItem(empty)
            return
        for row in tasks:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, self.ROW_HEIGHT))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, self._build_row(row))

    def _build_row(self, row) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        checkbox = QCheckBox()
        checkbox.setChecked(bool(row["done"]))
        checkbox.toggled.connect(
            lambda checked, tid=row["id"]: self.toggle_task.emit(tid, checked))
        layout.addWidget(checkbox)

        name_label = QLabel(row["name"])
        font = QFont()
        font.setStrikeOut(bool(row["done"]))
        name_label.setFont(font)
        name_label.setCursor(Qt.PointingHandCursor)
        name_label.mousePressEvent = (
            lambda event, tid=row["id"]: self.set_current_task.emit(tid))
        layout.addWidget(name_label, stretch=1)

        progress = QLabel(f"{row['completed']}/{row['estimated']} 🍅")
        progress.setObjectName("muted")
        layout.addWidget(progress)

        if self._current_task_id == row["id"] and not row["done"]:
            current_btn = QPushButton("★ 当前")
            current_btn.setObjectName("primary")
            current_btn.clicked.connect(lambda: self.set_current_task.emit(None))
        else:
            current_btn = QPushButton("设为当前")
            current_btn.clicked.connect(
                lambda _=False, tid=row["id"]: self.set_current_task.emit(tid))
        layout.addWidget(current_btn)

        delete_btn = QPushButton("🗑")
        delete_btn.setToolTip("删除任务")
        delete_btn.clicked.connect(
            lambda _=False, tid=row["id"]: self.delete_task.emit(tid))
        layout.addWidget(delete_btn)
        return w
