# -*- coding: utf-8 -*-
"""「专注期间应用使用」链路回归测试。

覆盖：番茄完成、顺计时停止 / 放弃、会话进行中切统计页、
多次增量落库不重复计数、短会话不丢数据。

运行：conda run -n self_clock python scripts/test_app_usage.py
全程使用临时数据库，不会触碰真实数据；采样间隔临时调为 1 秒以缩短耗时。
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import core.monitor as monitor_mod
monitor_mod.CHECK_INTERVAL_SEC = 1          # 加速采样，生产环境为 5 秒

from PySide6.QtCore import QEventLoop, QTimer           # noqa: E402
from PySide6.QtWidgets import QApplication              # noqa: E402

import app.main_window as mw_mod                        # noqa: E402
from app import theme                                   # noqa: E402
from core.sound import SoundPlayer                      # noqa: E402
from core.store import Store                            # noqa: E402
from core.timer import Phase                            # noqa: E402


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def total_seconds(store) -> float:
    return store.conn.execute(
        "SELECT COALESCE(SUM(seconds), 0) FROM app_usage").fetchone()[0]


class FakeDistractionDialog:
    """放弃弹窗替身：直接确认，避免测试阻塞。"""
    Accepted = 1
    reason = "测试分心"
    note = ""

    def __init__(self, *args, **kwargs):
        pass

    def exec(self):
        return self.Accepted


def main() -> int:
    app = QApplication(sys.argv)
    theme.set_theme("dark")
    data_dir = os.path.join(tempfile.mkdtemp(prefix="selfclock_usage_"), "data")
    store = Store(data_dir)
    win = mw_mod.MainWindow(store, SoundPlayer(os.path.join(ROOT, "assets")),
                            data_dir, os.path.join(ROOT, "assets"))
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(("  PASS  " if ok else "  FAIL  ") + label
              + (f"  [{detail}]" if detail else ""), flush=True)
        if not ok:
            failures.append(label)

    # A. 番茄钟完成
    print("[A] 番茄模式：完成一次专注", flush=True)
    before = total_seconds(store)
    win._on_start_requested()
    wait(2200)
    win.timer._stop_all()
    win._on_phase_finished(Phase.FOCUS, Phase.SHORT_BREAK, False)
    gained = total_seconds(store) - before
    check("完成后写入应用使用记录", gained > 1.0, f"{gained:.1f}s")

    # B. 顺计时停止（此前该路径漏了落库）
    print("[B] 顺计时模式：停止并记录", flush=True)
    win.stopwatch_mode = True
    before = total_seconds(store)
    win._on_stopwatch_start()
    wait(2200)
    win._on_stopwatch_stop()
    gained = total_seconds(store) - before
    check("顺计时停止写入应用使用记录", gained > 1.0, f"{gained:.1f}s")

    # C. 顺计时放弃（此前该路径同样漏了落库）
    print("[C] 顺计时模式：放弃", flush=True)
    mw_mod.DistractionDialog = FakeDistractionDialog
    before = total_seconds(store)
    win._on_stopwatch_start()
    wait(2200)
    win._on_stopwatch_abandon()
    gained = total_seconds(store) - before
    check("顺计时放弃写入应用使用记录", gained > 1.0, f"{gained:.1f}s")

    # D. 会话进行中切到统计页
    print("[D] 会话进行中查看统计页", flush=True)
    before = total_seconds(store)
    win._on_stopwatch_start()
    wait(2200)
    win._switch_page(3)
    rows = win.stats_view.app_bars._rows
    check("统计页立刻显示本次专注", len(rows) > 0, f"{len(rows)} 行")
    check("切页触发增量落库", total_seconds(store) > before)

    # E. 多次增量 flush 不重复计数
    print("[E] 增量落库不重复计数", flush=True)
    win._on_stopwatch_stop()               # 收掉 D 里仍在进行中的会话
    before = total_seconds(store)
    t0 = time.monotonic()
    win._on_stopwatch_start()
    wait(3200)
    for _ in range(3):
        win._flush_app_usage(min_seconds=0.05)
    win._on_stopwatch_stop()
    elapsed = time.monotonic() - t0
    gained = total_seconds(store) - before
    check("累计时长不超过真实经过时间", 1.0 < gained <= elapsed + 0.5,
          f"落库 {gained:.1f}s / 实际 {elapsed:.1f}s")

    # F. 短会话零头也要留下
    print("[F] 短会话", flush=True)
    before = total_seconds(store)
    win._on_stopwatch_start()
    wait(1200)
    win._on_stopwatch_stop()
    gained = total_seconds(store) - before
    check("短会话不丢数据", gained > 0.05, f"{gained:.2f}s")

    win.monitor.stop()
    store.close()
    print(("\n全部通过" if not failures else f"\n失败 {len(failures)} 项: {failures}"),
          flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
