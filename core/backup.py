# -*- coding: utf-8 -*-
"""自动备份：每日首次启动时把数据库复制到 backups/，保留最近 N 份。"""
import os
import sqlite3
import time
from datetime import date


def auto_backup(db_path: str, backups_dir: str, keep: int = 14) -> str | None:
    """当天尚未备份则备份一次；返回备份文件路径，未触发返回 None。"""
    os.makedirs(backups_dir, exist_ok=True)
    today_tag = date.today().strftime("%Y%m%d")
    for name in os.listdir(backups_dir):
        if name.startswith("selfclock_") and today_tag in name:
            return None
    dest = os.path.join(backups_dir,
                        f"selfclock_{today_tag}_{time.strftime('%H%M%S')}.db")
    # WAL 模式下直接复制主文件会漏数据，用 SQLite 备份 API（可与运行中的连接并存）
    src = sqlite3.connect(db_path)
    out = sqlite3.connect(dest)
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()
    _prune(backups_dir, keep)
    return dest


def _prune(backups_dir: str, keep: int) -> None:
    files = [os.path.join(backups_dir, n) for n in os.listdir(backups_dir)
             if n.startswith("selfclock_") and n.endswith(".db")]
    files.sort(key=os.path.getmtime, reverse=True)
    for old in files[keep:]:
        try:
            os.remove(old)
        except OSError:
            pass
