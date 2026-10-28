#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""make_wav.py — 从 MP3 生成预降增益的 WAV（对齐 opencode 的 attention.volume=0.4）

opencode 的音量是**播放时增益**，不碰系统音量。Windows 上 MCI 不支持逐流音量、
COM 端点音量不可用，所以这里用 ffmpeg 预先把 MP3 压成低增益 WAV，
播放时直接播 WAV —— 效果等价，且绝不污染系统音量。

用法:
  python make_wav.py                 # 用当前 soundbox.json 的 volume 重新生成
  python make_wav.py 0.5             # 指定增益重新生成
  python make_wav.py --show          # 显示 ffmpeg 探测到的时长
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOUNDS = os.path.join(HERE, "sounds")
WAVDIR = os.path.join(SOUNDS, "wav")
CONFIG = os.path.join(HERE, "soundbox.json")

# 候选 ffmpeg 位置
FFMPEG_CANDIDATES = [
    r"E:\Program Files\FFmpegFreeUI\ffmpeg.exe",
    r"E:\Program Files\Ani\app\ffmpeg.exe",
    r"E:\Program Files\Jianying_Pro\6.0.1.11779\ffmpeg.exe",
    "ffmpeg",
]


def find_ffmpeg():
    for c in FFMPEG_CANDIDATES:
        p = shutil.which(c) if os.path.basename(c) == "ffmpeg" else (c if os.path.isfile(c) else None)
        if p:
            return p
    return None


def current_volume():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return float(json.load(f).get("volume", 0.4))
    except Exception:
        return 0.4


def peak_db(ffmpeg, path):
    """量峰值电平 (dBFS)。量不到返回 None。"""
    try:
        r = subprocess.run([ffmpeg, "-hide_banner", "-i", path, "-af", "volumedetect",
                            "-f", "null", "-"], capture_output=True, text=True)
    except Exception:
        return None
    for line in r.stderr.splitlines():
        if "max_volume:" in line:
            try:
                return float(line.split("max_volume:")[1].split("dB")[0].strip())
            except ValueError:
                return None
    return None


# 归一化目标峰值：-1.5 dBFS 留一点余量防削波。
# 只乘固定系数会把本就小声的素材压得更听不见（Staplebops 原本峰值只有 -13 dB，
# 乘 0.4 后掉到 -24 dB，实测「响了但听不清」），所以改为逐文件按峰值拉齐。
TARGET_PEAK_DB = -1.5


def build(ffmpeg, gain):
    """gain: 0..1 的整体音量系数；每文件先按峰值归一化到 TARGET_PEAK_DB，再乘 gain。

    gain=1.0 即拉满（峰值 -1.5 dB）；0.5 约降 6 dB。不再直接拿 gain 当线性因子。
    """
    os.makedirs(WAVDIR, exist_ok=True)
    gain = max(0.01, min(1.0, float(gain)))   # 0 会让 ffmpeg 处理成静音，下限设 0.01
    gain_db = 20 * __import__("math").log10(gain)
    made = []
    for name in sorted(os.listdir(SOUNDS)):
        if not name.lower().endswith(".mp3"):
            continue
        src = os.path.join(SOUNDS, name)
        dst = os.path.join(WAVDIR, os.path.splitext(name)[0] + ".wav")
        p = peak_db(ffmpeg, src)
        if p is None:
            print("  SKIP %s: 量不到峰值" % name)
            continue
        vol_db = (TARGET_PEAK_DB - p) + gain_db
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
               "-i", src, "-af", "volume=%.2fdB" % vol_db,
               "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", dst]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print("  FAIL %s: %s" % (name, r.stderr.strip()[:200]))
            continue
        made.append(os.path.basename(dst))
    return made


def show(ffmpeg):
    for d in (SOUNDS, WAVDIR):
        if not os.path.isdir(d):
            continue
        print("[%s]" % d)
        for n in sorted(os.listdir(d)):
            if not n.lower().endswith((".mp3", ".wav")):
                continue
            p = os.path.join(d, n)
            r = subprocess.run([ffmpeg, "-hide_banner", "-i", p, "-f", "null", "-"],
                               capture_output=True, text=True)
            dur = ""
            for line in r.stderr.splitlines():
                if "time=" in line:
                    dur = line.split("time=")[1].split()[0]
            print("  %-24s %8d B  %s" % (n, os.path.getsize(p), dur))


def main(argv):
    ff = find_ffmpeg()
    if not ff:
        print("!! 找不到 ffmpeg，无法生成 WAV。")
        print("   请安装 ffmpeg 或把路径加入 make_wav.py 的 FFMPEG_CANDIDATES。")
        return 1
    print("ffmpeg: %s" % ff)
    if "--show" in argv:
        show(ff)
        return 0
    gain = None
    for a in argv[1:]:
        try:
            gain = float(a)
            break
        except ValueError:
            pass
    if gain is None:
        gain = current_volume()
    gain = max(0.0, min(1.0, gain))
    print("增益: %s" % gain)
    made = build(ff, gain)
    print("已生成 %d 个 WAV:" % len(made))
    for m in made:
        print("  %s" % m)
    # 同步落盘 volume
    try:
        with open(CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    cfg["volume"] = gain
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
