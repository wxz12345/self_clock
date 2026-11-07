# -*- coding: utf-8 -*-
"""真机诊断脚本：真实显示模式下自动开始一次专注，连续截图对比。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.pop("QT_QPA_PLATFORM", None)  # 真实显示

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.theme import build_qss
from core.store import Store
from core.sound import SoundPlayer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = QApplication(sys.argv)
app.setStyleSheet(build_qss())
store = Store(os.path.join(BASE_DIR, "data"))
sound = SoundPlayer(os.path.join(BASE_DIR, "assets"))
from app.main_window import MainWindow  # noqa: E402

win = MainWindow(store, sound, os.path.join(BASE_DIR, "data"))
win.resize(1120, 760)
win.show()
win.raise_()
win.activateWindow()
os.makedirs("preview", exist_ok=True)

plan = [
    ("t1_idle", 1200),
    ("t2_running_3s", 4500),
    ("t3_running_8s", 5000),
    ("t4_running_15s", 7000),
]
state = {"i": 0}


def grab():
    name, _ = plan[state["i"]]
    win.grab().save(f"preview/dbg_{name}.png")
    print("saved", name, flush=True)
    state["i"] += 1
    if state["i"] < len(plan):
        QTimer.singleShot(plan[state["i"]][1], grab)
    else:
        # 结束：放弃本次测试专注（不留脏数据），退出
        try:
            if win.session_id is not None:
                store.finish_session(win.session_id, "skipped", 0)
                win.session_id = None
            win.timer._stop_all()
        except Exception:
            pass
        win.monitor.stop()
        app.quit()


def start_focus():
    win._switch_page(0)
    print(">>> 模拟点击 开始专注", flush=True)
    win.focus_view.start_requested.emit()
    print(">>> timer.running =", win.timer.running, flush=True)
    print(">>> ring.text =", repr(win.focus_view.ring._time_text), flush=True)
    QTimer.singleShot(plan[0][1], grab)


QTimer.singleShot(1500, start_focus)
app.exec()
store.close()
print("EXPERIMENT DONE", flush=True)
os._exit(0)
