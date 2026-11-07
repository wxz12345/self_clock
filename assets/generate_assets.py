# -*- coding: utf-8 -*-
"""生成应用音效素材（仅标准库，可随时重新运行覆盖）。

提示音为 44100Hz / 16bit / 单声道 wav：
- bell.wav     专注阶段结束：清脆的"叮"（双泛音钟声）
- chime.wav    休息阶段结束：柔和三音上行琶音
- coin.wav     获得金币：经典"金币音"（B5→E6 短促双音）
- reminder.wav 提醒事项：双短哔提示

白噪音为 22050Hz 无缝循环 wav（尾→首交叉淡化拼接）：
- noise_rain.wav   雨声：低通白噪音 + 随机雨滴
- noise_brown.wav  棕噪音：积分白噪音的低沉底噪
- noise_fire.wav   篝火：棕噪音底 + 随机爆裂声
- noise_waves.wav  海浪：低通噪音 + 10 秒周期起伏
"""
import math
import os
import random
import struct
import wave

RATE = 44100
RATE2 = 22050
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def synth(duration, fn, gain=0.8):
    frames = bytearray()
    n = int(RATE * duration)
    for i in range(n):
        t = i / RATE
        v = fn(t, duration)
        v = max(-1.0, min(1.0, v * gain))
        frames += struct.pack("<h", int(v * 32767))
    return bytes(frames)


def write_wav(name, data, rate=RATE):
    path = os.path.join(OUT_DIR, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data)
    print("written", path)


def decay(t, dur, k=6.0):
    return math.exp(-k * t / dur)


def bell_note(freq):
    def fn(t, dur):
        env = decay(t, dur, k=5.0)
        s = (math.sin(2 * math.pi * freq * t) * 0.7
             + math.sin(2 * math.pi * freq * 2.01 * t) * 0.25
             + math.sin(2 * math.pi * freq * 2.99 * t) * 0.12)
        return s * env
    return fn


def bell():
    return synth(1.3, bell_note(880.0), gain=0.85)


def chime():
    notes = [(1046.5, 0.0), (1318.5, 0.22), (1568.0, 0.44)]  # C6 E6 G6
    total = 1.4

    def fn(t, dur):
        s = 0.0
        for freq, start in notes:
            if t >= start:
                lt = t - start
                env = math.exp(-4.0 * lt)
                s += (math.sin(2 * math.pi * freq * lt) * 0.55
                      + math.sin(2 * math.pi * freq * 2 * lt) * 0.15) * env
        return s
    return synth(total, fn, gain=0.7)


def coin():
    total = 0.22

    def fn(t, dur):
        if t < 0.08:
            freq, env = 987.8, 1.0
        else:
            freq, env = 1318.5, 1.0
        s = math.sin(2 * math.pi * freq * t) * 0.5
        sq = 0.2 * (1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0)
        s = s + sq
        return s * env * decay(t, dur, k=3.0)
    return synth(total, fn, gain=0.6)


def reminder():
    total = 0.5

    def fn(t, dur):
        if 0.0 <= t < 0.12 or 0.22 <= t < 0.34:
            env = min(1.0, 20.0 * (t % 0.22)) * math.exp(-2.0 * (t % 0.22))
            return math.sin(2 * math.pi * 660.0 * t) * 0.6 * env
        return 0.0
    return synth(total, fn, gain=0.75)


def main():
    write_wav("bell.wav", bell())
    write_wav("chime.wav", chime())
    write_wav("coin.wav", coin())
    write_wav("reminder.wav", reminder())
    # 白噪音中的"棕噪音"保留合成版（纯数学噪音不存在压缩音质损失），
    # 雨声/海浪/篝火/风声改用 assets/noise/ 下的真实录音 mp3（见 CREDITS.md）
    write_wav(os.path.join("noise", "brown.wav"), brown_noise(), rate=RATE2)


# ==================== 白噪音（22050Hz 无缝循环） ====================

def synth2(samples, gain=0.8):
    """float 列表 -> 16bit PCM 字节。"""
    frames = bytearray()
    peak = max(1e-9, max(abs(v) for v in samples))
    scale = gain / peak
    for v in samples:
        v = max(-1.0, min(1.0, v * scale))
        frames += struct.pack("<h", int(v * 32767))
    return bytes(frames)


def loopify(samples, fade=0.5):
    """把素材尾部与前部交叉淡化，得到无缝循环（长度缩短 fade 秒）。"""
    n = len(samples)
    f = int(RATE2 * fade)
    out = list(samples[: n - f])
    for i in range(f):
        w = i / f
        out[i] = out[i] * w + samples[n - f + i] * (1 - w)
    return out


def _looped(gen, gain=0.75):
    return synth2(loopify(gen), gain=gain)


def rain():
    n = RATE2 * 10
    out = [0.0] * n
    y = 0.0
    for i in range(n):
        y += 0.16 * (random.uniform(-1, 1) - y)   # 一阶低通
        out[i] = y * 1.5
    for _ in range(int(10 * 12)):                  # 雨滴
        pos = random.randrange(n)
        amp = random.uniform(0.04, 0.16)
        freq = random.uniform(1600, 3400)
        for k in range(int(0.03 * RATE2)):
            if pos + k < n:
                out[pos + k] += amp * math.sin(2 * math.pi * freq * k / RATE2) \
                    * math.exp(-40 * k / RATE2)
    return _looped(out)


def brown_noise():
    n = RATE2 * 10
    out = [0.0] * n
    y = 0.0
    for i in range(n):
        y = (y + random.uniform(-1, 1) * 0.02) * 0.998
        out[i] = y * 6.0
    # 去直流
    mean = sum(out) / n
    return _looped([v - mean for v in out], gain=0.7)


def fire():
    n = RATE2 * 10
    base = brown_noise_base(n)
    for _ in range(int(10 * 9)):                   # 爆裂声
        pos = random.randrange(n)
        amp = random.uniform(0.15, 0.55)
        freq = random.uniform(700, 4200)
        dur = random.uniform(0.008, 0.03)
        for k in range(int(dur * RATE2)):
            if pos + k < n:
                base[pos + k] += amp * math.sin(2 * math.pi * freq * k / RATE2) \
                    * math.exp(-18 * k / RATE2) * (1 if random.random() > 0.5 else -1)
    return _looped(base, gain=0.7)


def brown_noise_base(n):
    out = [0.0] * n
    y = 0.0
    for i in range(n):
        y = (y + random.uniform(-1, 1) * 0.02) * 0.998
        out[i] = y * 4.0
    mean = sum(out) / n
    return [v - mean for v in out]


def waves():
    n = RATE2 * 10
    out = [0.0] * n
    y = 0.0
    for i in range(n):
        y += 0.045 * (random.uniform(-1, 1) - y)   # 更闷的低通
        env = 0.55 + 0.45 * math.cos(2 * math.pi * i / n - math.pi)  # 10s 周期，首尾同值
        out[i] = y * env * 2.2
    return _looped(out)


if __name__ == "__main__":
    main()
