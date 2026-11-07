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
    "theme": "dark",            # dark / light
    "categories": '["科研", "课程", "琐事", "娱乐", "休息"]',
    "last_category": "科研",
    "break_reminder_enabled": "0",   # 规律性久坐提醒
    "break_reminder_min": "60",
    "break_reminder_text": "站起来活动活动，记得多喝水 🚰",
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
"""


class Store:
    def __init__(self, data_dir: str):
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "selfclock.db")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
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

    def distraction_reason_counts(self, days: int | None = 30):
        sql = ("SELECT reason, COUNT(*) AS n FROM distractions")
        args: list = []
        if days is not None:
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

    def top_app_usage(self, days: int = 30, limit: int = 8):
        since = time.time() - days * 86400
        return self.conn.execute(
            "SELECT process, SUM(seconds) AS s FROM app_usage WHERE ts >= ? "
            "GROUP BY process ORDER BY s DESC LIMIT ?",
            (since, limit)).fetchall()

    def category_minutes(self, days: int = 30):
        """近 N 天 focus 会话按归类的专注分钟。"""
        since = time.time() - days * 86400
        return self.conn.execute(
            "SELECT COALESCE(NULLIF(category, ''), '未分类') AS cat, "
            "COALESCE(SUM(actual_min), 0) AS m FROM sessions "
            "WHERE type='focus' AND status IN ('completed','abandoned') "
            "AND start_ts >= ? GROUP BY cat ORDER BY m DESC",
            (since,)).fetchall()

    def weekday_hour_minutes(self, days: int = 90):
        """热力图数据：[(星期 0=周一…6=周日, 小时, 分钟)]。"""
        since = time.time() - days * 86400
        rows = self.conn.execute(
            "SELECT (CAST(strftime('%w', start_ts, 'unixepoch', 'localtime') "
            "AS INTEGER) + 6) % 7 AS wd, "
            "CAST(strftime('%H', start_ts, 'unixepoch', 'localtime') AS INTEGER) "
            "AS hr, SUM(actual_min) AS m FROM sessions "
            "WHERE type='focus' AND status IN ('completed','abandoned') "
            "AND start_ts >= ? GROUP BY wd, hr", (since,)).fetchall()
        return [(r["wd"], r["hr"], r["m"]) for r in rows]

    def best_focus_day(self, days: int = 7):
        """本周专注分钟最高的一天：[(date_str, minutes)] 取 top1。"""
        since = time.time() - days * 86400
        return self.conn.execute(
            "SELECT date(start_ts, 'unixepoch', 'localtime') AS d, "
            "SUM(actual_min) AS m FROM sessions "
            "WHERE type='focus' AND status IN ('completed','abandoned') "
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
        shutil.copy2(self.db_path, path)

    def restore_from(self, path: str) -> None:
        """用备份覆盖当前数据库。调用方负责之后重启应用。"""
        self.conn.commit()
        self.conn.close()
        shutil.copy2(path, self.db_path)

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
            "WHERE type='focus' AND status='completed' AND start_ts >= ? "
            "GROUP BY d", (since,)).fetchall()
        return {r["d"]: r["n"] for r in rows}

    def daily_focus_minutes(self, days: int = 30) -> list[tuple[str, float]]:
        """近 N 天每天的专注分钟数（含放弃的会话的实际时长）。"""
        since = time.time() - days * 86400
        rows = self.conn.execute(
            "SELECT date(start_ts, 'unixepoch', 'localtime') AS d, "
            "COALESCE(SUM(actual_min), 0) AS m FROM sessions "
            "WHERE type='focus' AND status IN ('completed','abandoned') "
            "AND start_ts >= ? GROUP BY d", (since,)).fetchall()
        return [(r["d"], r["m"]) for r in rows]

    def today_pomodoros(self) -> int:
        since = self._day_start(date.today())
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM sessions "
            "WHERE type='focus' AND status='completed' AND start_ts >= ?",
            (since,)).fetchone()
        return row["n"]

    def total_pomodoros(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM sessions "
            "WHERE type='focus' AND status='completed'").fetchone()
        return row["n"]

    def focus_summary(self) -> tuple[float, float, float]:
        """返回 (今日专注分钟, 累计专注分钟, 完成率 0~1)。"""
        today_since = self._day_start(date.today())
        row = self.conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN start_ts>=? THEN actual_min END),0) "
            "AS today_m, COALESCE(SUM(actual_min),0) AS total_m, "
            "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS c, "
            "SUM(CASE WHEN status='abandoned' THEN 1 ELSE 0 END) AS a "
            "FROM sessions WHERE type='focus' "
            "AND status IN ('completed','abandoned')",
            (today_since,)).fetchone()
        done, abandoned = row["c"] or 0, row["a"] or 0
        rate = done / (done + abandoned) if (done + abandoned) else 0.0
        return row["today_m"] or 0.0, row["total_m"] or 0.0, rate
