# -*- coding: utf-8 -*-
"""滚轮守卫 / 白噪音混音器滚轮行为回归测试。

覆盖：普通下拉框仍防误触；混音器音色下拉框可用滚轮；
数值框仍须先点选；混音器列表标签/按钮区域滚轮可滚动；
音量滑块滚轮仍可微调。

运行：conda run -n self_clock python scripts/test_wheel_guard.py
全程使用临时数据库与假播放器，不触碰真实数据、不播放声音。
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt       # noqa: E402
from PySide6.QtGui import QMouseEvent, QWheelEvent           # noqa: E402
from PySide6.QtWidgets import (QApplication, QComboBox,       # noqa: E402
                               QLabel, QPushButton, QScrollArea,
                               QSlider, QSpinBox)
from app.noise_mixer import NoiseMixerDialog                 # noqa: E402
from app.wheel_guard import install_wheel_guard              # noqa: E402
from core.sound import DEFAULT_VOLUME, NOISES                # noqa: E402
from core.store import Store                                 # noqa: E402


class FakeSound:
    """只记账不发声的播放器替身。"""

    def __init__(self, mix):
        self._levels = dict(mix)

    def get_mix(self):
        return dict(self._levels)

    def set_noise_level(self, name, level):
        self._levels[name] = level

    def remove_noise(self, name):
        self._levels.pop(name, None)

    def has_noise(self, name):
        return True

    def stop_noise(self):
        self._levels.clear()


def wheel(widget, delta=-120) -> bool:
    ev = QWheelEvent(QPointF(10.0, 10.0), QPointF(10.0, 10.0),
                     QPoint(0, 0), QPoint(0, delta),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                     Qt.ScrollPhase.NoScrollPhase, False)
    return QApplication.sendEvent(widget, ev)


def under_scroll(widget) -> bool:
    w = widget
    while w is not None:
        if isinstance(w, QScrollArea):
            return True
        w = w.parent()
    return False


def main() -> int:
    app = QApplication(sys.argv)
    install_wheel_guard(app)
    store = Store(os.path.join(tempfile.mkdtemp(prefix="wheel_test_"), "data"))
    mix = {n: DEFAULT_VOLUME for n in NOISES[:12]}
    dlg = NoiseMixerDialog(FakeSound(mix), store)
    dlg.resize(420, 260)
    dlg.show()
    app.processEvents()
    app.processEvents()

    failures: list[str] = []

    def check(label, ok, detail=""):
        print(("  PASS  " if ok else "  FAIL  ") + label
              + (f"  [{detail}]" if detail else ""), flush=True)
        if not ok:
            failures.append(label)

    # 1. 全局规则未回退：普通下拉框仍禁用滚轮
    print("[1] 全局守卫规则", flush=True)
    plain = QComboBox()
    plain.addItems(["甲", "乙", "丙"])
    i0 = plain.currentIndex()
    wheel(plain)
    check("普通下拉框仍禁滚轮", plain.currentIndex() == i0,
          f"{i0} -> {plain.currentIndex()}")

    spin = QSpinBox()
    spin.setRange(0, 100)
    spin.setValue(50)
    v0 = spin.value()
    wheel(spin)
    check("数值框未点选时滚轮无效", spin.value() == v0,
          f"{v0} -> {spin.value()}")
    press = QMouseEvent(QEvent.MouseButtonPress, QPointF(5.0, 5.0),
                        QPointF(5.0, 5.0), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(spin, press)
    wheel(spin)
    check("数值框点选后滚轮生效", spin.value() != v0,
          f"{v0} -> {spin.value()}")

    # 2. 混音器音色下拉框：局部豁免后滚轮可切换
    print("[2] 混音器音色下拉框", flush=True)
    combo = dlg.available_combo
    check("豁免属性已设置", bool(combo.property("wheelGuardExempt")))
    check("下拉框有可选项", combo.count() > 1 and combo.isEnabled(),
          f"{combo.count()} 项")
    i0 = combo.currentIndex()
    wheel(combo)
    check("滚轮可切换音色", combo.currentIndex() != i0,
          f"{i0} -> {combo.currentIndex()}")

    # 3. 列表滚动：标签 / 按钮区域
    print("[3] 混音器列表滚轮", flush=True)
    scroll = dlg.findChild(QScrollArea)
    sb = scroll.verticalScrollBar()
    check("列表内容超出可视高度", sb.maximum() > 0, f"0..{sb.maximum()}")

    row_labels = [w for w in dlg.findChildren(QLabel) if under_scroll(w)]
    sb.setValue(0)
    app.processEvents()
    wheel(row_labels[0])
    app.processEvents()
    check("标签区域滚轮可滚动列表", sb.value() > 0, f"-> {sb.value()}")

    row_btns = [w for w in dlg.findChildren(QPushButton) if under_scroll(w)]
    sb.setValue(0)
    app.processEvents()
    wheel(row_btns[0])
    app.processEvents()
    check("按钮区域滚轮可滚动列表", sb.value() > 0, f"-> {sb.value()}")

    # 4. 音量滑块：保留滚轮微调
    print("[4] 音量滑块", flush=True)
    slider = dlg.findChild(QSlider)
    v0 = slider.value()
    wheel(slider)
    app.processEvents()
    check("滑块滚轮仍可调音量", slider.value() != v0,
          f"{v0} -> {slider.value()}")

    store.close()
    print("\n全部通过" if not failures else f"\n失败 {len(failures)} 项: {failures}",
          flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
