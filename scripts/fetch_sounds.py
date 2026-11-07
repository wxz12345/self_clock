# -*- coding: utf-8 -*-
"""从 Freesound 拉取用户指定的 10 个音源：抓元数据/许可证、下载、声道检查入库。"""
import os
import re
import subprocess
import tempfile

import soundfile as sf

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
NOISE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "assets", "noise")

# (sound_id, 存储键, 用户标签)
WANT = [
    ("737922", "storm1", "雷雨①"),
    ("859141", "storm2", "雷雨②"),
    ("817285", "storm3", "雷雨③"),
    ("369547", "storm4", "雷雨④"),
    ("874803", "storm5", "雷雨⑤"),
    ("338374", "pure_thunder", "纯雷声"),
    ("548381", "pure_rain1", "纯雨声①"),
    ("536843", "pure_rain2", "纯雨声②"),
    ("519573", "pure_rain3", "纯雨声③"),
    ("746877", "crickets", "虫鸣"),
]


def curl(url, out=None, timeout=180):
    args = ["curl", "-sL", "-A", UA, "--max-time", str(timeout), url]
    if out:
        args += ["-o", out]
    r = subprocess.run(args, capture_output=True, text=not out)
    return r.stdout if not out else os.path.getsize(out) if os.path.exists(out) else 0


def page_meta(sound_id):
    html = curl(f"https://freesound.org/s/{sound_id}/")
    title = re.search(r"<title>Freesound - ([^<]+)</title>", html)
    lic = re.search(r"(https://creativecommons.org/[^\"&]+)", html)
    mp3 = re.search(r'data-mp3="([^"]+)"', html)
    return (title.group(1).strip() if title else "?",
            lic.group(1) if lic else "?",
            mp3.group(1) if mp3 else None)


def analyze(path):
    info = sf.info(path)
    data, sr = sf.read(path)
    dur = info.frames / sr
    if data.ndim == 1:
        return dur, 1, 1.0
    n = min(len(data), sr * 15)
    l = (sum(x * x for x in data[:n, 0]) / n) ** 0.5
    r = (sum(x * x for x in data[:n, 1]) / n) ** 0.5
    return dur, 2, max(l, r) / max(1e-9, min(l, r))


def rebalance_to_stereo(path):
    """单声道→双声道复制；左右失衡→拉平能量。统一输出 44.1k/48k 立体声 mp3。"""
    data, sr = sf.read(path)
    if data.ndim == 1:
        data = [(x, x) for x in data]
    else:
        n = min(len(data), sr * 15)
        l = (sum(x * x for x in data[:n, 0]) / n) ** 0.5
        r = (sum(x * x for x in data[:n, 1]) / n) ** 0.5
        if max(l, r) / max(1e-9, min(l, r)) > 1.5:
            g_l, g_r = 1.0 / max(l, 1e-9) ** 0.5, 1.0 / max(r, 1e-9) ** 0.5
            g_l = g_l ** 0.5 if False else (max(l, r) ** -0.5) * (max(l, r) / l) ** 0.5
            # 简单归一：让两通道 RMS 相等，总体响度不变
            gain_l, gain_r = ((l + r) / 2) ** 0.5 / max(l, 1e-9), ((l + r) / 2) ** 0.5 / max(r, 1e-9)
            data = [(x[0] * gain_l, x[1] * gain_r) for x in data]
    out = path.replace(".mp3", "_bal.mp3")
    sf.write(out, data, sr, format="MP3")
    os.replace(out, path)


def main():
    rows = []
    for sid, key, label in WANT:
        print(f"--- {label} ({sid}) ---", flush=True)
        name, lic_url, mp3 = page_meta(sid)
        name = re.sub(r"\s+by\s+[^|]*$", "", name).strip()
        if not mp3:
            print("!! 未找到预览地址，跳过", flush=True)
            continue
        hq = mp3.replace("-lq.mp3", "-hq.mp3")
        tmp = os.path.join(tempfile.gettempdir(), f"fs_{key}.mp3")
        curl(hq, out=tmp)
        dur, ch, ratio = analyze(tmp)
        rebal = ""
        if ratio > 1.6:
            rebalance_to_stereo(tmp)
            dur, ch, ratio = analyze(tmp)
            rebal = "（已做声道平衡）"
        os.replace(tmp, os.path.join(NOISE_DIR, f"{key}.mp3"))
        lic_name = ("CC0" if "/zero/" in lic_url else
                    "CC-BY 4.0" if "/by/4" in lic_url else
                    "CC-BY 3.0" if "/by/3" in lic_url else
                    "CC-BY-NC" if "nc" in lic_url else lic_url)
        rows.append((key, label, name, sid, lic_name, dur, ch, ratio, rebal))
        print(f"OK {key}.mp3 | {name[:45]} | {lic_name} | {dur:.0f}s | 声道{ch} | L/R={ratio:.2f}{rebal}", flush=True)

    print("\n===== CREDITS 表格数据 =====")
    for key, label, name, sid, lic_name, dur, ch, ratio, rebal in rows:
        print(f"| {key}.mp3 {label} | [{name}](https://freesound.org/s/{sid}/) | {lic_name} | {dur:.0f}s |")


if __name__ == "__main__":
    main()
