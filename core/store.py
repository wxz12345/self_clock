# -*- coding: utf-8 -*-
"""SQLite 存储层。所有读写都在主线程（由 main_window 统一调度），无需加锁。

时间戳一律存 Unix 秒（float），日期分组用 SQLite 的 localtime 转换。
"""
import json
import os
import shutil
import sqlite3
import time
from datetime import date, timedelta

DEFAULTS = {
    "work_min": "45",
    "short_break_min": "5",
    "long_break_min": "15",
    "rounds_before_long": "4",
    "daily_goal": "6",
    "sound_enabled": "1",
    "auto_start_breaks": "1",
    "blacklist": "[]",
    "coins": "0",
    "last_goal_date": "",
    "close_action": "ask",      # ask / tray / exit：点 X 时最小化到托盘还是退出
    "white_noise": "off",       # 旧字段，保留兼容；混音器用 noise_mix
    "noise_mix": "",            # JSON {name: volume 0~1}
    "mini_pos": "",             # 迷你窗位置 "x,y"
    "mini_opacity": "100",      # 迷你窗内容透明度百分比
    "theme": "dark",            # dark / light
    "categories": '["科研", "课程", "琐事", "娱乐", "休息"]',
    "last_category": "科研",
    "timer_mode": "pomodoro",       # pomodoro / stopwatch
    "break_reminder_enabled": "0",   # 规律性久坐提醒
    "break_reminder_min": "60",
    "break_reminder_text": "站起来活动活动，记得多喝水 🚰",
    "update_check_enabled": "0",    # 启动时检查新版本（联网，默认关闭）
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    estimated INTEGER DEFAULT 1,
    completed INTEGER DEFAULT 0,
    done INTEGER DEFAULT 0,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    type TEXT NOT NULL,             -- focus / short_break / long_break
    start_ts REAL NOT NULL,
    end_ts REAL,
    planned_min REAL NOT NULL,
    actual_min REAL,
    status TEXT DEFAULT 'running',  -- running / completed / abandoned / skipped
    category TEXT DEFAULT ''        -- 计时归类（科研/课程/琐事/娱乐/休息…）
);
CREATE TABLE IF NOT EXISTS distractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    ts REAL NOT NULL,
    reason TEXT NOT NULL,
    note TEXT DEFAULT '',
    source TEXT DEFAULT 'manual'    -- manual / blacklist
);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    event_ts REAL,
    location TEXT DEFAULT '',
    note TEXT DEFAULT '',
    remind_ts REAL NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending / reminded / done
    created_at REAL
);
CREATE TABLE IF NOT EXISTS coins_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    amount INTEGER NOT NULL,
    reason TEXT
);
CREATE TABLE IF NOT EXISTS app_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    ts REAL NOT NULL,
    process TEXT NOT NULL,
    seconds REAL NOT NULL
);
-- 今天之前的 app_usage 明细按"天+进程"汇总后存这里（见 compact_app_usage）
CREATE TABLE IF NOT EXISTS app_usage_daily (
    day TEXT NOT NULL,              -- 本地日期 YYYY-MM-DD
    process TEXT NOT NULL,
    seconds REAL NOT NULL,
    PRIMARY KEY (day, process)
);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_ts);
CREATE INDEX IF NOT EXISTS idx_distractions_ts ON distractions(ts);
CREATE INDEX IF NOT EXISTS idx_app_usage_ts ON app_usage(ts);
"""


class Store:
    def __init__(self, data_dir: str):
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "selfclock.db")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        # 旧库迁移：sessions 可能没有 category 列
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(sessions)")}
        if "category" not in cols:
            self.conn.execute(
                "ALTER TABLE sessions ADD COLUMN category TEXT DEFAULT ''")
            self.conn.commit()
        # 补齐默认设置（不覆盖已有值）
        for key, value in DEFAULTS.items():
            self.conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                (key, value))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---------- 设置 ----------
    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get_setting(key, str(default)))
        except (TypeError, ValueError):
            return default

    def set_setting(self, key: str, value) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)))
        self.conn.commit()

    def get_blacklist(self) -> list[str]:
        try:
            return json.loads(self.get_setting("blacklist", "[]"))
        except json.JSONDecodeError:
            return []

    def set_blacklist(self, items: list[str]) -> None:
        self.set_setting("blacklist", json.dumps(items, ensure_ascii=False))

    # ---------- 任务 ----------
    def add_task(self, name: str, estimated: int) -> None:
        self.conn.execute(
            "INSERT INTO tasks(name, estimated, created_at) VALUES(?, ?, ?)",
            (name.strip(), estimated, time.time()))
        self.conn.commit()

    def get_tasks(self, include_done: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM tasks"
        if not include_done:
            sql += " WHERE done=0"
        sql += " ORDER BY done, created_at DESC"
        return self.conn.execute(sql).fetchall()

    def set_task_done(self, task_id: int, done: bool) -> None:
        self.conn.execute("UPDATE tasks SET done=? WHERE id=?",
                          (1 if done else 0, task_id))
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()

    def increment_task_pomodoro(self, task_id: int) -> None:
        self.conn.execute(
            "UPDATE tasks SET completed = completed + 1 WHERE id=?",
            (task_id,))
        self.conn.commit()

    # ---------- 会话 ----------
    def start_session(self, task_id, type_: str, planned_min: float,
                      category: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions(task_id, type, start_ts, planned_min, category) "
            "VALUES(?, ?, ?, ?, ?)",
            (task_id, type_, time.time(), planned_min, category))
        self.conn.commit()
        return cur.lastrowid

    def finish_session(self, session_id: int, status: str,
                       actual_min: float) -> None:
        self.conn.execute(
            "UPDATE sessions SET end_ts=?, actual_min=?, status=? WHERE id=?",
            (time.time(), round(actual_min, 2), status, session_id))
        self.conn.commit()

    def open_running_session(self) -> sqlite3.Row | None:
        """应用启动时找回上次没结束的会话（异常退出遗留，标记为放弃）。"""
        return self.conn.execute(
            "SELECT * FROM sessions WHERE status='running' "
            "ORDER BY id DESC LIMIT 1").fetchone()

    # ---------- 分心记录 ----------
    def add_distraction(self, session_id, reason: str, note: str = "",
                        source: str = "manual") -> None:
        self.conn.execute(
            "INSERT INTO distractions(session_id, ts, reason, note, source) "
            "VALUES(?, ?, ?, ?, ?)",
            (session_id, time.time(), reason, note, source))
        self.conn.commit()

    @staticmethod
    def _day_range(day: str) -> tuple[float, float]:
        """本地日期 YYYY-MM-DD -> [当天 0 点, 次日 0 点) 的时间戳区间。"""
        d = date.fromisoformat(day)
        return (time.mktime(d.timetuple()),
                time.mktime((d + timedelta(days=1)).timetuple()))

    def distraction_reason_counts(self, days: int | None = 30,
                                  day: str | None = None):
        """分心原因计数；传 day（YYYY-MM-DD）只统计当天，否则近 N 天。"""
        sql = ("SELECT reason, COUNT(*) AS n FROM distractions")
        args: list = []
        if day is not None:
            lo, hi = self._day_range(day)
            sql += " WHERE ts >= ? AND ts < ?"
            args += [lo, hi]
        elif days is not None:
            sql += " WHERE ts >= ?"
            args.append(time.time() - days * 86400)
        sql += " GROUP BY reason ORDER BY n DESC"
        return self.conn.execute(sql, args).fetchall()

    # ---------- 应用使用 ----------
    def add_app_usage(self, session_id, process: str, seconds: float) -> None:
        self.conn.execute(
            "INSERT INTO app_usage(session_id, ts, process, seconds) "
            "VALUES(?, ?, ?, ?)",
            (session_id, time.time(), process, round(seconds, 1)))
        self.conn.commit()

    def compact_app_usage(self) -> int:
        """把今天之前的 app_usage 明细按"本地日期+进程"汇总进 app_usage_daily，
        并删除已汇总的明细。幂等，可重复调用；返回被汇总的明细行数。"""
        today_start = self._day_start(date.today())
        rows = self.conn.execute(
            "SELECT date(ts, 'unixepoch', 'localtime') AS d, process, "
            "SUM(seconds) AS s, COUNT(*) AS n FROM app_usage "
            "WHERE ts < ? GROUP BY d, process", (today_start,)).fetchall()
        if not rows:
            return 0
        for r in rows:
            self.conn.execute(
                "INSERT INTO app_usage_daily(day, process, seconds) "
                "VALUES(?,?,?) ON CONFLICT(day, process) DO UPDATE SET "
                "seconds = seconds + excluded.seconds",
                (r["d"], r["process"], r["s"]))
        self.conn.execute("DELETE FROM app_usage WHERE ts < ?", (today_start,))
        self.conn.commit()
        return sum(r["n"] for r in rows)

    def top_app_usage(self, days: int = 30, limit: int = 8,
                      day: str | None = None):
        """应用使用 Top N（秒）：同时读今日明细与历史按天汇总。
        传 day 只统计当天，否则近 N 天（含今天）。"""
        if day is not None:
            lo, hi = self._day_range(day)
            first = last = day
        else:
            lo, hi = time.time() - days * 86400, float("inf")
            first = date.fromtimestamp(lo).isoformat()
            last = date.today().isoformat()
        return self.conn.execute(
            "SELECT process, SUM(s) AS s FROM ("
            " SELECT process, seconds AS s FROM app_usage"
            "  WHERE ts >= ? AND ts < ?"
            " UNION ALL"
            " SELECT process, seconds AS s FROM app_usage_daily"
            "  WHERE day >= ? AND day <= ?"
            ") GROUP BY process ORDER BY s DESC LIMIT ?",
            (lo, hi, first, last, limit)).fetchall()

    def category_minutes(self, days: int = 30, day: str | None = None):
        """focus 会话按归类的专注分钟；传 day 只统计当天，否则近 N 天。"""
        if day is not None:
            lo, hi = self._day_range(day)
        else:
            lo, hi = time.time() - days * 86400, float("inf")
        return self.conn.execute(
            "SELECT COALESCE(NULLIF(category, ''), '未分类') AS cat, "
            "COALESCE(SUM(actual_min), 0) AS m FROM sessions "
            "WHERE type IN ('focus','stopwatch') AND status IN ('completed','abandoned') "
            "AND start_ts >= ? AND start_ts < ? GROUP BY cat ORDER BY m DESC",
            (lo, hi)).fetchall()

    def weekday_hour_minutes(self, days: int = 90):
        """热力图数据：[(星期 0=周一…6=周日, 小时, 分钟)]。"""
        since = time.time() - days * 86400
        rows = self.conn.execute(
            "SELECT (CAST(strftime('%w', start_ts, 'unixepoch', 'localtime') "
            "AS INTEGER) + 6) % 7 AS wd, "
            "CAST(strftime('%H', start_ts, 'unixepoch', 'localtime') AS INTEGER) "
            "AS hr, SUM(actual_min) AS m FROM sessions "
            "WHERE type IN ('focus','stopwatch') AND status IN ('completed','abandoned') "
            "AND start_ts >= ? GROUP BY wd, hr", (since,)).fetchall()
        return [(r["wd"], r["hr"], r["m"]) for r in rows]

    def best_focus_day(self, days: int = 7):
        """本周专注分钟最高的一天：[(date_str, minutes)] 取 top1。"""
        since = time.time() - days * 86400
        return self.conn.execute(
            "SELECT date(start_ts, 'unixepoch', 'localtime') AS d, "
            "SUM(actual_min) AS m FROM sessions "
            "WHERE type IN ('focus','stopwatch') AND status IN ('completed','abandoned') "
            "AND start_ts >= ? GROUP BY d ORDER BY m DESC LIMIT 1",
            (since,)).fetchone()

    def clear_records(self, records: bool = True, usage: bool = True,
                      coins: bool = True, tasks: bool = True) -> None:
        """按类清空数据（用于清除测试数据；不可恢复，建议先备份）。"""
        if records:
            self.conn.execute("DELETE FROM sessions")
            self.conn.execute("DELETE FROM distractions")
        if usage:
            self.conn.execute("DELETE FROM app_usage")
            self.conn.execute("DELETE FROM app_usage_daily")
        if coins:
            self.conn.execute("DELETE FROM coins_log")
            self.set_setting("coins", 0)
            self.set_setting("last_goal_date", "")
        if tasks:
            self.conn.execute("DELETE FROM tasks")
            self.set_setting("current_task", "")
        self.conn.commit()

    # ---------- 金币 ----------
    def get_coins(self) -> int:
        return self.get_int("coins", 0)

    def add_coins(self, amount: int, reason: str) -> None:
        self.conn.execute(
            "INSERT INTO coins_log(ts, amount, reason) VALUES(?, ?, ?)",
            (time.time(), amount, reason))
        self.set_setting("coins", self.get_coins() + amount)

    # ---------- 提醒 ----------
    def add_reminder(self, title: str, event_ts, location: str,
                     note: str, remind_ts: float) -> int:
        cur = self.conn.execute(
            "INSERT INTO reminders(title, event_ts, location, note, "
            "remind_ts, status, created_at) VALUES(?, ?, ?, ?, ?, 'pending', ?)",
            (title, event_ts, location, note, remind_ts, time.time()))
        self.conn.commit()
        return cur.lastrowid

    def get_reminders(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM reminders "
            "ORDER BY status='done', remind_ts").fetchall()

    def due_reminders(self, now: float | None = None) -> list[sqlite3.Row]:
        now = now or time.time()
        return self.conn.execute(
            "SELECT * FROM reminders WHERE status='pending' AND remind_ts<=? "
            "ORDER BY remind_ts", (now,)).fetchall()

    def mark_reminder_reminded(self, reminder_id: int) -> None:
        self.conn.execute(
            "UPDATE reminders SET status='reminded' WHERE id=?", (reminder_id,))
        self.conn.commit()

    def snooze_reminder(self, reminder_id: int, seconds: int = 300) -> None:
        self.conn.execute(
            "UPDATE reminders SET status='pending', remind_ts=? WHERE id=?",
            (time.time() + seconds, reminder_id))
        self.conn.commit()

    def complete_reminder(self, reminder_id: int) -> None:
        self.conn.execute(
            "UPDATE reminders SET status='done' WHERE id=?", (reminder_id,))
        self.conn.commit()

    def delete_reminder(self, reminder_id: int) -> None:
        self.conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
        self.conn.commit()

    # ---------- 备份 / 导出 ----------
    def backup_to(self, path: str) -> None:
        self.conn.commit()
        # WAL 模式下直接复制主文件会漏掉 -wal 里的新数据，改用 SQLite 备份 API
        dest = sqlite3.connect(path)
        try:
            self.conn.backup(dest)
        finally:
            dest.close()

    def restore_from(self, path: str) -> None:
        """用备份覆盖当前数据库。调用方负责之后重启应用。"""
        self.conn.commit()
        self.conn.close()
        shutil.copy2(path, self.db_path)
        for suffix in ("-wal", "-shm"):   # 清掉旧库遗留的日志，避免与新库错配
            try:
                os.remove(self.db_path + suffix)
            except OSError:
                pass

    def merge_from(self, path: str) -> dict:
        """把备份数据合并进当前库：id 全部重映射，按业务键去重，
        设置不合并（保留当前）。返回各类新增条数。"""
        b = sqlite3.connect(path)
        b.row_factory = sqlite3.Row
        stats = {"tasks": 0, "sessions": 0, "distractions": 0,
                 "app_usage": 0, "reminders": 0, "coins": 0}

        # ---- 任务（去重键：name + created_at）----
        task_map = {}
        for r in b.execute("SELECT * FROM tasks ORDER BY id"):
            ex = self.conn.execute(
                "SELECT id FROM tasks WHERE name=? AND created_at=?",
                (r["name"], r["created_at"])).fetchone()
            if ex:
                task_map[r["id"]] = ex["id"]
                continue
            cur = self.conn.execute(
                "INSERT INTO tasks(name, estimated, completed, done, created_at)"
                " VALUES(?,?,?,?,?)",
                (r["name"], r["estimated"], r["completed"], r["done"],
                 r["created_at"]))
            task_map[r["id"]] = cur.lastrowid
            stats["tasks"] += 1

        # ---- 会话（去重键：type + start_ts）----
        sess_map = {}
        for r in b.execute("SELECT * FROM sessions ORDER BY id"):
            ex = self.conn.execute(
                "SELECT id FROM sessions WHERE type=? AND start_ts=?",
                (r["type"], r["start_ts"])).fetchone()
            if ex:
                sess_map[r["id"]] = ex["id"]
                continue
            cur = self.conn.execute(
                "INSERT INTO sessions(task_id, type, start_ts, end_ts,"
                " planned_min, actual_min, status, category)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (task_map.get(r["task_id"]), r["type"], r["start_ts"],
                 r["end_ts"], r["planned_min"], r["actual_min"],
                 r["status"], r["category"]))
            sess_map[r["id"]] = cur.lastrowid
            stats["sessions"] += 1

        # ---- 分心（去重键：ts + reason + source）----
        for r in b.execute("SELECT * FROM distractions ORDER BY id"):
            if self.conn.execute(
                    "SELECT 1 FROM distractions WHERE ts=? AND reason=?"
                    " AND source=?",
                    (r["ts"], r["reason"], r["source"])).fetchone():
                continue
            self.conn.execute(
                "INSERT INTO distractions(session_id, ts, reason, note, source)"
                " VALUES(?,?,?,?,?)",
                (sess_map.get(r["session_id"]), r["ts"], r["reason"],
                 r["note"], r["source"]))
            stats["distractions"] += 1

        # ---- 应用使用（去重键：ts + process）----
        for r in b.execute("SELECT * FROM app_usage ORDER BY id"):
            if self.conn.execute(
                    "SELECT 1 FROM app_usage WHERE ts=? AND process=?",
                    (r["ts"], r["process"])).fetchone():
                continue
            self.conn.execute(
                "INSERT INTO app_usage(session_id, ts, process, seconds)"
                " VALUES(?,?,?,?)",
                (sess_map.get(r["session_id"]), r["ts"], r["process"],
                 r["seconds"]))
            stats["app_usage"] += 1

        # ---- 应用使用按天汇总（去重键：day + process；旧备份可能没有此表）----
        try:
            daily_rows = b.execute("SELECT * FROM app_usage_daily").fetchall()
        except sqlite3.OperationalError:
            daily_rows = []
        for r in daily_rows:
            if self.conn.execute(
                    "SELECT 1 FROM app_usage_daily WHERE day=? AND process=?",
                    (r["day"], r["process"])).fetchone():
                continue
            self.conn.execute(
                "INSERT INTO app_usage_daily(day, process, seconds)"
                " VALUES(?,?,?)", (r["day"], r["process"], r["seconds"]))
            stats["app_usage"] += 1

        # ---- 提醒（去重键：title + remind_ts）----
        for r in b.execute("SELECT * FROM reminders ORDER BY id"):
            if self.conn.execute(
                    "SELECT 1 FROM reminders WHERE title=? AND remind_ts=?",
                    (r["title"], r["remind_ts"])).fetchone():
                continue
            self.conn.execute(
                "INSERT INTO reminders(title, event_ts, location, note,"
                " remind_ts, status, created_at) VALUES(?,?,?,?,?,?,?)",
                (r["title"], r["event_ts"], r["location"], r["note"],
                 r["remind_ts"], r["status"], r["created_at"]))
            stats["reminders"] += 1

        # ---- 金币流水（去重键：ts + amount + reason）；余额 = 当前 + 新增净额
        net = 0
        for r in b.execute("SELECT * FROM coins_log ORDER BY id"):
            if self.conn.execute(
                    "SELECT 1 FROM coins_log WHERE ts=? AND amount=? AND reason=?",
                    (r["ts"], r["amount"], r["reason"])).fetchone():
                continue
            self.conn.execute(
                "INSERT INTO coins_log(ts, amount, reason) VALUES(?,?,?)",
                (r["ts"], r["amount"], r["reason"]))
            net += r["amount"]
            stats["coins"] += 1
        if net:
            self.set_setting("coins", self.get_coins() + net)

        self.conn.commit()
        b.close()
        return stats

    def app_usage_daily_for_export(self):
        """应用使用按天汇总（历史汇总表 + 今天的明细），按日期、时长降序。"""
        return self.conn.execute(
            "SELECT day, process, SUM(s) AS seconds FROM ("
            " SELECT day, process, seconds AS s FROM app_usage_daily"
            " UNION ALL"
            " SELECT date(ts, 'unixepoch', 'localtime') AS day, process,"
            "  seconds AS s FROM app_usage"
            ") GROUP BY day, process ORDER BY day DESC, seconds DESC").fetchall()

    def sessions_for_export(self):
        return self.conn.execute(
            "SELECT s.id, s.type, s.start_ts, s.end_ts, s.planned_min, "
            "s.actual_min, s.status, COALESCE(t.name, '') AS task_name "
            "FROM sessions s LEFT JOIN tasks t ON t.id = s.task_id "
            "ORDER BY s.id").fetchall()

    def distractions_for_export(self):
        return self.conn.execute(
            "SELECT id, session_id, ts, reason, note, source "
            "FROM distractions ORDER BY id").fetchall()

    # ---------- 统计 ----------
    @staticmethod
    def _day_start(day: date) -> float:
        return time.mktime(day.timetuple())

    def daily_pomodoros(self, days: int = 400) -> dict[str, int]:
        since = time.time() - days * 86400
        rows = self.conn.execute(
            "SELECT date(start_ts, 'unixepoch', 'localtime') AS d, "
            "COUNT(*) AS n FROM sessions "
            "WHERE type IN ('focus','stopwatch') AND status='completed' AND start_ts >= ? "
            "GROUP BY d", (since,)).fetchall()
        return {r["d"]: r["n"] for r in rows}

    def daily_focus_minutes(self, days: int = 30) -> list[tuple[str, float]]:
        """近 N 天每天的专注分钟数（含放弃的会话的实际时长）。"""
        since = time.time() - days * 86400
        rows = self.conn.execute(
            "SELECT date(start_ts, 'unixepoch', 'localtime') AS d, "
            "COALESCE(SUM(actual_min), 0) AS m FROM sessions "
            "WHERE type IN ('focus','stopwatch') AND status IN ('completed','abandoned') "
            "AND start_ts >= ? GROUP BY d", (since,)).fetchall()
        return [(r["d"], r["m"]) for r in rows]

    def today_pomodoros(self) -> int:
        since = self._day_start(date.today())
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM sessions "
            "WHERE type IN ('focus','stopwatch') AND status='completed' AND start_ts >= ?",
            (since,)).fetchone()
        return row["n"]

    def total_pomodoros(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM sessions "
            "WHERE type IN ('focus','stopwatch') AND status='completed'").fetchone()
        return row["n"]

    def focus_summary(self) -> tuple[float, float, float]:
        """返回 (今日专注分钟, 累计专注分钟, 完成率 0~1)。"""
        today_since = self._day_start(date.today())
        row = self.conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN start_ts>=? THEN actual_min END),0) "
            "AS today_m, COALESCE(SUM(actual_min),0) AS total_m, "
            "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS c, "
            "SUM(CASE WHEN status='abandoned' THEN 1 ELSE 0 END) AS a "
            "FROM sessions WHERE type IN ('focus','stopwatch') "
            "AND status IN ('completed','abandoned')",
            (today_since,)).fetchone()
        done, abandoned = row["c"] or 0, row["a"] or 0
        rate = done / (done + abandoned) if (done + abandoned) else 0.0
        return row["today_m"] or 0.0, row["total_m"] or 0.0, rate
