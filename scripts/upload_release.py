# -*- coding: utf-8 -*-
"""通过 GitHub API 创建 release 并上传 zip 资产。

凭证从 Windows 凭证管理器（git credential fill）获取，仅本地使用、不打印。
"""
import json
import subprocess
import sys
import urllib.request

REPO = "wxz12345/self_clock"
TAG = sys.argv[1] if len(sys.argv) > 1 else "v1.0.0"
ASSET = f"dist/SelfClock_{TAG}_win64.zip"
ASSET_NAME = f"SelfClock_{TAG}_win64.zip"

NOTES = """## 自律番茄钟 — 桌面即下即用版

**下载即用**：下载下方 zip，解压后双击 `SelfClock.exe`（免安装、免 Python 环境）。

### 本版亮点
- 🍅 番茄钟（45/5/15 默认可自定义）+ 任务 + 每日目标与连击 + 树生长游戏化
- 🏷️ 计时归类（科研/课程/琐事/娱乐/休息，可自定义）+ 分类分布统计
- 🧘 温和自控：放弃必须选分心原因；黑名单前台窗口检测
- 🎧 白噪音混音器：8 种真实录音，多轨叠加独立音量
- 🎯 迷你窗接管模式；⏰ 提醒事项 + 规律性久坐提醒
- 📊 统计三页签：概览 / 周趋势（时段热力图）/ 周回顾
- 🌗 深浅色主题完整适配（含托盘菜单）；卡片投影与过渡动画
- 💾 每日自动备份、CSV 导出、按类清空、单实例保护、开机自启（可选）

### 说明
- 数据全部本地存储（exe 旁 `data/` 目录），无需登录
- 素材来源见 [CREDITS.md](https://github.com/wxz12345/self_clock/blob/main/CREDITS.md)
"""


def get_token() -> str:
    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, check=True)
    for line in result.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise RuntimeError("未找到 GitHub 凭证")


def api(url: str, token: str, data=None, headers=None, method=None,
        timeout: int = 600):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"token {token}")
    req.add_header("User-Agent", "self_clock-release")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    body = data if isinstance(data, bytes) else (
        json.dumps(data).encode() if data else None)
    with urllib.request.urlopen(req, body, timeout=timeout) as resp:
        content = resp.read().decode()
        return json.loads(content) if content else {}


def main() -> None:
    token = get_token()
    print("凭证获取 OK")

    # 已有同名 release 则复用
    releases = api(f"https://api.github.com/repos/{REPO}/releases", token)
    release = next((r for r in releases if r["tag_name"] == TAG), None)
    if release:
        print(f"release {TAG} 已存在（id={release['id']}），复用")
    else:
        release = api(
            f"https://api.github.com/repos/{REPO}/releases", token,
            data={"tag_name": TAG, "target_commitish": "main",
                  "name": f"{TAG} 首个公开版本", "body": NOTES, "draft": False,
                  "prerelease": False})
        print(f"release 创建 OK (id={release['id']})")

    # 检查资产是否已存在
    if any(a["name"] == ASSET_NAME for a in release.get("assets", [])):
        print("资产已存在，跳过上传")
        return
    print("开始上传 zip（93MB，可能需要几分钟）...")
    with open(ASSET, "rb") as f:
        asset = api(
            f"https://uploads.github.com/repos/{REPO}/releases/"
            f"{release['id']}/assets?name={ASSET_NAME}",
            token, data=f.read(),
            headers={"Content-Type": "application/zip"})
    print(f"资产上传 OK: {asset['browser_download_url']}")


if __name__ == "__main__":
    sys.exit(main())
