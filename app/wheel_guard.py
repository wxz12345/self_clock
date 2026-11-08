# -*- coding: utf-8 -*-
"""滚轮防误触：统一约束 QComboBox / QSpinBox 的滚轮行为。

规则（对应"点击选中后再滚轮才有效"）：
- QComboBox（主题、关闭行为、分类、任务、提醒时机等）：**完全禁用滚轮**
- QSpinBox / QDateTimeEdit：**只有点击过该控件**之后，滚轮才调整数值
  （仅"有焦点"不够——切页时 Qt 会自动把焦点给第一个控件）
- QSlider 等其它控件不受影响（音量滑块本就该用滚轮）
- 例外：控件声明 `wheelGuardExempt` 动态属性后跳过守卫（目前只有白噪音
  混音器的音色下拉框使用，选项多，滚轮浏览更顺手）

注意：QSpinBox 内部有 QLineEdit 子控件，点击事件常由子控件接收，
因此判断时沿父链向上找真正的 SpinBox/ComboBox。
"""
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import (QAbstractSpinBox, QComboBox, QDateTimeEdit,
                               QDoubleSpinBox, QSpinBox)

SPIN_TYPES = (QAbstractSpinBox, QSpinBox, QDoubleSpinBox, QDateTimeEdit)


def _find_ancestor(obj, types):
    """沿父链查找指定类型的控件（含自身）。"""
    w = obj
    while w is not None:
        if isinstance(w, types):
            return w
        w = w.parent()
    return None


def _is_exempt(obj) -> bool:
    """控件（或其祖先）声明 wheelGuardExempt 时，跳过守卫拦截。

    用于个别确实需要滚轮的下拉框，例如白噪音混音器的音色选择器：
    它有十几个选项，滚轮浏览比逐个点开更顺手。全局规则不变，
    只有显式声明的控件才豁免。
    """
    w = obj
    while w is not None:
        if w.property("wheelGuardExempt"):
            return True
        w = w.parent()
    return False


class WheelGuard(QObject):
    """装在 QApplication 上，拦截所有滚轮事件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clicked_spin = None   # 最近一次被点击的数值/时间输入框

    def eventFilter(self, obj, event) -> bool:
        etype = event.type()

        # 记录"被点击的数值框"（点击事件可能落在其内部子控件上）
        if etype in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
            self._clicked_spin = _find_ancestor(obj, SPIN_TYPES)
            return False

        if etype != QEvent.Wheel:
            return False

        # 显式豁免的控件优先放行（如混音器的音色下拉框）
        if _is_exempt(obj):
            return False

        # 下拉框：滚轮一律不改变选中项
        if _find_ancestor(obj, (QComboBox,)) is not None:
            return True

        # 数值/时间输入框：必须被点击过才允许滚轮
        spin = _find_ancestor(obj, SPIN_TYPES)
        if spin is not None:
            return spin is not self._clicked_spin

        return False


def install_wheel_guard(app) -> None:
    """在 QApplication 上安装滚轮守卫（保持引用，避免被回收）。"""
    guard = WheelGuard(app)
    app.installEventFilter(guard)
    app._wheel_guard = guard   # 持有引用
