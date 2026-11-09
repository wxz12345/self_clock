# -*- coding: utf-8 -*-
"""可选的新版本检查：只读请求 GitHub 公开 API，不发送任何用户数据。

默认关闭（设置 update_check_enabled=0），由用户在设置页显式开启。
"""
import json
import re
import urllib.request

from PySide6.QtCore import QThread, Signal

REPO = "wxz12345/self_clock"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
TIMEOUT_SEC = 5


def parse_version(text: str) -> tuple[int, ...]:
    """'v2.0.1' / '2.0' -> (2, 0, 1) / (2, 0)；解析不出数字返回 ()。"""
    return tuple(int(n) for n in re.findall(r"\d+", text.split("-")[0])[:4])


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    if not a or not b:
        return False
    width = max(len(a), len(b))
    a += (0,) * (width - len(a))
    b += (0,) * (width - len(b))
    return a > b


def fetch_latest() -> tuple[str, str] | None:
    """返回 (tag, 页面 URL)；网络失败/格式异常返回 None。"""
    req = urllib.request.Request(
        API_URL, headers={"User-Agent": "SelfClock-update-check",
                          "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return str(data["tag_name"]), str(data.get("html_url", ""))
    except Exception:   # 离线、限流、格式变化：静默忽略，不影响使用
        return None


class UpdateChecker(QThread):
    found = Signal(str, str)     # (最新 tag, release 页面 URL)

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self._current = current_version

    def run(self) -> None:
        result = fetch_latest()
        if result and is_newer(result[0], self._current):
            self.found.emit(*result)
