# -*- coding: utf-8 -*-
"""专注期间的应用使用累计：纯逻辑，不依赖 Qt / UI，便于单元测试。

采样点由监控线程用 time.monotonic() 生成并传入；本类把「上一个采样点 → 本次」
的真实时长记到上一个前台进程名下，再以增量方式写入 store.add_app_usage。
"""
import time
from collections.abc import Callable


class UsageTracker:
    def __init__(self, store, clock: Callable[[], float] = time.monotonic):
        self._store = store
        self._clock = clock
        self._session_id: int | None = None
        self._acc: dict[str, float] = {}
        self._last_name: str | None = None
        self._last_ts: float = 0.0
        self._paused = False

    # ---------- 生命周期 ----------
    @property
    def session_id(self) -> int | None:
        return self._session_id

    def is_tracking(self, current_session_id: int | None) -> bool:
        """current_session_id 是否就是正在被跟踪的会话。"""
        return (current_session_id is not None
                and current_session_id == self._session_id)

    @property
    def paused(self) -> bool:
        return self._paused

    def begin(self, session_id: int | None) -> None:
        self._session_id = session_id
        self._paused = False
        self._acc.clear()
        self._last_name = None
        self._last_ts = self._clock()

    def pause(self, current_session_id: int | None) -> None:
        """专注暂停：先把暂停前的时长结算落库，之后到恢复前不再累计。"""
        if not self.is_tracking(current_session_id) or self._paused:
            return
        self.flush(current_session_id, 0.05)
        self._paused = True

    def resume(self) -> None:
        """专注恢复：从此刻重新起算，暂停期间的时间不计入任何进程。"""
        if not self._paused:
            return
        self._paused = False
        self._last_ts = self._clock()
        self._last_name = None

    def end(self, current_session_id: int | None, min_seconds: float = 0.05) -> None:
        """最终结算并停止跟踪；必须在会话 id 置空之前调用。"""
        self.flush(current_session_id, min_seconds)
        self._session_id = None

    # ---------- 采样与落库 ----------
    def on_sample(self, current_session_id: int | None, name: str,
                  sampled_at: float) -> None:
        if not self.is_tracking(current_session_id) or self._paused:
            return
        if sampled_at <= self._last_ts:
            # 采样在 flush 之前生成、却因信号排队滞后到达：这段时间已经
            # 结算落库，只更新当前进程名，避免下一段把它重复计一次
            self._last_name = name
            return
        owner = self._last_name or name
        # 首个采样点把「会话开始 → 本次采样」也归给当前进程，不丢开头这段
        self._acc[owner] = (self._acc.get(owner, 0.0)
                            + max(0.0, sampled_at - self._last_ts))
        self._last_name = name
        self._last_ts = sampled_at

    def flush(self, current_session_id: int | None,
              min_seconds: float = 0.5) -> None:
        """把累计时长以增量写入数据库；可反复调用，不会重复计数。
        min_seconds 是写入门槛，收尾场景放低到 0.05 秒。"""
        if not self.is_tracking(current_session_id) or self._paused:
            return
        now = self._clock()
        if self._last_name:
            delta = max(0.0, now - self._last_ts)
            if delta:
                self._acc[self._last_name] = (
                    self._acc.get(self._last_name, 0.0) + delta)
            # 从这一刻重新起算，下一段不会把已落库的时长重复计入
            self._last_ts = now
        if not self._acc:
            return
        leftover: dict[str, float] = {}
        for name, seconds in self._acc.items():
            if seconds >= min_seconds:
                self._store.add_app_usage(current_session_id, name, seconds)
            else:
                leftover[name] = seconds   # 不足门槛的零头留着，下次累加后再写
        self._acc = leftover
