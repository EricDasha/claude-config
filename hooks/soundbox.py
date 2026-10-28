#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""soundbox.py — Claude Code 提示音控制台（Windows，零第三方依赖）

对齐 opencode「设置 → 音效」面板的三通道模型：
    智能体 (agent)      当智能体完成或需要注意时播放声音
    权限   (permissions) 当需要权限时播放声音
    错误   (errors)      发生错误时播放声音

每个通道独立：enabled 开关 + 音效 ID（45 选 1）+ 独立音量。
音效素材取自 opencode 官方仓库 packages/ui/src/assets/audio/*.mp3。

用法:
  python soundbox.py                       交互式控制台
  python soundbox.py status                查看当前配置
  python soundbox.py doctor                自检：hook 挂载 / 事件名 / 素材 / 配置
  python soundbox.py list                  列出全部可用音效（45 个）
  python soundbox.py play <id>             播放一次
  python soundbox.py hook <event>          供 Claude Code hook 调用
  python soundbox.py set <通道> <id>       设置某通道的音效
  python soundbox.py enable <通道> on|off   开关某通道
  python soundbox.py volume <0..1>          全局音量（重建预压 WAV）
  python soundbox.py mute on|off            总静音

通道: agent(智能体) / permissions(权限) / errors(错误)
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SOUNDS = os.path.join(HERE, "sounds")
WAVDIR = os.path.join(SOUNDS, "wav")
CONFIG = os.path.join(HERE, "soundbox.json")
CATALOG = os.path.join(HERE, "sounds.json")

# ---------------------------------------------------------------------------
# 通道定义 —— 对齐 opencode settings.sounds.{agent,permissions,errors}
#   key      : 配置键
#   title    : 面板标题（opencode i18n settings.general.sounds.<k>.title）
#   desc     : 面板描述（opencode i18n settings.general.sounds.<k>.description）
#   events   : 触发该通道的 Claude Code hook 事件名
# ---------------------------------------------------------------------------
CHANNELS = {
    "agent": {
        "title": "智能体",
        "desc": "当智能体完成或需要注意时播放声音",
        # 直接事件 —— Stop 只在该轮真的停下时响，见 _stop_is_prompt。
        # SubagentStop 不挂：子智能体结束不是「需要你介入」，它是后台噪音源。
        "events": ["Stop"],
        # 由 Notification 的 notification_type 派生的子集
        # idle_prompt：Claude 在等你输入却一直没等到，才是真正需要注意
        "notify_types": ["agent_completed", "agent_needs_input", "idle_prompt"],
    },
    "permissions": {
        "title": "权限",
        "desc": "当需要权限时播放声音",
        "events": [],
        # elicitation_*：MCP 请求式对话框，同样在等你点「允许/拒绝」
        "notify_types": ["permission_prompt", "worker_permission_prompt",
                         "elicitation_dialog", "elicitation_url_dialog"],
    },
    "errors": {
        "title": "错误",
        "desc": "发生错误时播放声音",
        "events": ["StopFailure", "PostToolUseFailure"],
        "notify_types": [],
    },
}
CHANNEL_ORDER = ["agent", "permissions", "errors"]

DEFAULTS = {
    "agentEnabled": True,
    "agent": "staplebops-01",
    "permissionsEnabled": True,
    "permissions": "staplebops-02",
    "errorsEnabled": True,
    "errors": "nope-03",
    "volume": 0.4,
}

# hook 事件 → 通道。事件名带 Notification:<type> 表示按 notification_type 细分。
EVENT_TO_CHANNEL = {}
for _ch, _meta in CHANNELS.items():
    for _ev in _meta["events"]:
        EVENT_TO_CHANNEL[_ev] = _ch

# notification_type → 通道
NOTIFY_TO_CHANNEL = {}
for _ch, _meta in CHANNELS.items():
    for _nt in _meta["notify_types"]:
        NOTIFY_TO_CHANNEL[_nt] = _ch

# 各通道去抖秒数（防连响）。key = 事件标识，逐事件独立计数。
# Stop 与 Notification:agent_completed 同属 agent 通道但语义不同
# （本轮结束 vs 后台智能体完成），必须分开去抖，否则后者的信号会被前者吞掉。
DEBOUNCE = {
    "Stop": 2.0,
    "SubagentStop": 2.0,
    "Notification:agent": 2.0,
    "Notification:permissions": 1.0,
    "StopFailure": 2.0,
    "PostToolUseFailure": 2.0,
}

# StopFailure.error 里这些值不是「出错了」，是用户自己按了 Esc。
# 按 Esc 却在耳边炸 Nope 03，才是「莫名其妙突然响起」。
STOP_FAILURE_BENIGN = {"aborted", "user_interrupt", "interrupted"}

# 父代理在替子代理收尾 / 空闲通知时会带着这些 notification_type 发 Stop。
SUBAGENT_STOP_TYPES = {"agent_completed", "agent_needs_input", "idle_prompt"}

# trace 默认开启：本工具此前「该响不响 / 乱响」全靠猜，日志是唯一证据。
# 设 SOUNDBOX_TRACE=0 可关。

# doctor 的响度底线（峰值 dBFS）。低于此值视为「播了也听不见」。
# -40 是保守阈值：正常提示音峰值在 -25 左右，坏素材会是 -60 上下。
PEAK_FLOOR_DB = -40.0


def load_catalog():
    """音效清单：{id: {label: 中文名, file: mp3 文件名}}"""
    try:
        with open(CATALOG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def sound_ids():
    cat = load_catalog()
    if cat:
        return sorted(cat)
    # 兜底：扫目录
    if not os.path.isdir(SOUNDS):
        return []
    return sorted(os.path.splitext(n)[0] for n in os.listdir(SOUNDS)
                  if n.lower().endswith(".mp3"))


def label_of(sid):
    cat = load_catalog()
    return (cat.get(sid) or {}).get("label", sid)


def resolve(sid):
    """音效 ID → 可播放文件路径。优先用预降增益的 WAV，回退原始 MP3。"""
    if not sid:
        return ""
    base = os.path.splitext(os.path.basename(str(sid)))[0]
    for cand in (os.path.join(WAVDIR, base + ".wav"),
                 os.path.join(SOUNDS, base + ".mp3")):
        if os.path.isfile(cand):
            return cand
    return os.path.join(WAVDIR, base + ".wav")


def play(sid, wait=True):
    path = resolve(sid)
    if not os.path.isfile(path):
        return False
    winmm = ctypes.windll.winmm
    alias = "sbx%d" % os.getpid()
    kind = "waveaudio" if path.lower().endswith(".wav") else "mpegvideo"
    if winmm.mciSendStringW('open "%s" type %s alias %s' % (path, kind, alias),
                             None, 0, 0) != 0:
        return False
    winmm.mciSendStringW("play %s%s" % (alias, " wait" if wait else ""), None, 0, 0)
    winmm.mciSendStringW("close %s" % alias, None, 0, 0)
    return True


def spawn(sid):
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "play", sid],
                     creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def debounce(key, seconds):
    p = os.path.join(os.environ.get("TEMP", HERE), "claude-notify-%s.last" % key)
    now = time.time()
    last = 0.0
    try:
        with open(p) as f:
            last = float((f.read() or "0").strip())
    except Exception:
        pass
    if now - last < seconds:
        return False
    try:
        with open(p, "w") as f:
            f.write(str(now))
    except Exception:
        pass
    return True


# ---------------------------------------------------------------------------
# hook 入口
# ---------------------------------------------------------------------------

def _classify(event, payload):
    """把 hook 事件 + payload 归到一个通道。返回 (channel, why)。

    event 形如:
        "Stop" / "SubagentStop" / "StopFailure" / "PostToolUseFailure"   直接事件
        "Notification"                                                     按 notification_type 派发
    """
    if event == "Notification":
        ntype = payload.get("notification_type", "")
        ch = NOTIFY_TO_CHANNEL.get(ntype)
        if ch is None:
            return None, "notification_type=%s 不映射任何通道" % ntype
        return ch, ""
    ch = EVENT_TO_CHANNEL.get(event)
    if ch is None:
        return None, "未知事件"
    return ch, ""


def _stop_is_prompt(payload):
    """Stop 是否代表「真的要你介入了」。返回 (bool, why)。

    有三类 Stop 不是：
      a) 后台任务仍在跑（background_tasks 非空）—— 会话只是被挂起等唤醒
      b) 还有 cron / ScheduleWakeup / loop 要唤醒 —— 同上
      c) 父代理替子代理收尾（payload 带子代理标记，或 notification_type 是
         agent_* / idle_prompt）—— 子代理结束不等于要你介入
    """
    tasks = payload.get("background_tasks")
    if isinstance(tasks, list) and tasks:
        return False, "后台任务仍在跑 (%d 个)" % len(tasks)
    crons = payload.get("session_crons")
    if isinstance(crons, list) and crons:
        return False, "还有 %d 个定时/唤醒待触发" % len(crons)
    nt = payload.get("notification_type", "")
    if nt in SUBAGENT_STOP_TYPES:
        return False, "父代理替子代理收尾 (notification_type=%s)" % nt
    if payload.get("agent_id") or payload.get("parent_tool_use_id"):
        return False, "子代理的 Stop"
    return True, ""


def hook(event, payload=None):
    if os.environ.get("CLAUDE_NOTIFY_SOUND") == "off":
        return 0
    cfg = load_config()
    if cfg.get("mute"):
        return 0
    payload = payload or {}

    channel, why = _classify(event, payload)
    if channel is None:
        _trace("skip", event, why)
        return 0
    if not cfg.get(channel + "Enabled", True):
        _trace("skip", event, "通道 %s 已停用" % channel)
        return 0

    # 每通道的前置闸：不是所有同名事件都值得吵醒人
    if event == "Stop":
        ok, why = _stop_is_prompt(payload)
        if not ok:
            _trace("skip", event, "不该打断: " + why)
            return 0
    if event == "StopFailure":
        err = str(payload.get("error", "")).lower()
        if err in STOP_FAILURE_BENIGN:
            _trace("skip", event, "用户中断 (%s)，不算错误" % err)
            return 0
    if event == "PostToolUseFailure":
        if payload.get("is_interrupt"):
            _trace("skip", event, "用户中断，不算错误")
            return 0

    sid = cfg.get(channel)
    # 运行环境可临时覆盖（对齐 opencode 的 sounds 覆盖语义）
    env = os.environ.get("CLAUDE_NOTIFY_SOUND")
    if env and env != "off":
        sid = env

    path = resolve(sid)
    if not os.path.isfile(path):
        sys.stderr.write("[soundbox] 音效无效: %r（通道 %s）\n" % (sid, channel))
        return 1

    dkey = _debounce_key(event, channel)
    if debounce(dkey, DEBOUNCE.get(dkey, 2.0)):
        _trace("play", event, "%s -> %s (%s)" % (channel, sid, label_of(sid)))
        spawn(sid)
    else:
        _trace("skip", event, "去抖抑制 (%s)" % dkey)
    return 0


def peak_db(path):
    """峰值电平 (dBFS)。用 ffmpeg volumedetect 量，量不到返回 None。

    存在的意义：WAV 是预压产物，增益/素材任一出问题都会变成「响了但听不见」，
    而这种故障不会报错，只能靠量。
    """
    ff = _find_ffmpeg()
    if not ff:
        return None
    try:
        r = subprocess.run([ff, "-hide_banner", "-i", path, "-af", "volumedetect",
                            "-f", "null", "-"],
                           capture_output=True, text=True, timeout=20)
    except Exception:
        return None
    for line in r.stderr.splitlines():
        if "max_volume:" in line:
            try:
                return float(line.split("max_volume:")[1].split("dB")[0].strip())
            except ValueError:
                return None
    return None


def _find_ffmpeg():
    import shutil
    for c in (r"E:\Program Files\FFmpegFreeUI\ffmpeg.exe",
              r"E:\Program Files\Ani\app\ffmpeg.exe",
              r"E:\Program Files\Jianying_Pro\6.0.1.11779\ffmpeg.exe"):
        if os.path.isfile(c):
            return c
    return shutil.which("ffmpeg")


def _debounce_key(event, channel):
    """去抖键：Notification 按通道细分，其余按事件名细分。"""
    if event == "Notification":
        return "Notification:%s" % channel
    return event


def _trace(action, event, detail):
    """可观测性：写一行日志，便于确认 hook 真的触发并归到了正确通道。
    默认开启（SOUNDBOX_TRACE=0 关闭），写 %TEMP%\\claude-soundbox.log。"""
    if os.environ.get("SOUNDBOX_TRACE") == "0":
        return
    try:
        p = os.path.join(os.environ.get("TEMP", HERE), "claude-soundbox.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write("%s %-8s %-34s %s\n" % (
                time.strftime("%H:%M:%S"), action, event, detail))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 展示
# ---------------------------------------------------------------------------

def channel_state(cfg, ch):
    on = bool(cfg.get(ch + "Enabled", True))
    sid = cfg.get(ch) or DEFAULTS[ch]
    return on, sid, label_of(sid)


def status():
    cfg = load_config()
    print("音效目录 : %s" % SOUNDS)
    print("配置文件 : %s" % CONFIG)
    print("可用音效 : %d 个" % len(sound_ids()))
    print()
    for ch in CHANNEL_ORDER:
        meta = CHANNELS[ch]
        on, sid, lab = channel_state(cfg, ch)
        trig = list(meta["events"]) + ["Notification:" + t for t in meta["notify_types"]]
        print("[%s] %s —— %s" % (ch, meta["title"], meta["desc"]))
        print("    状态   : %s" % ("启用" if on else "停用"))
        print("    音效   : %s  (%s)" % (sid, lab))
        print("    触发   : %s" % ", ".join(trig))
        print()
    print("音量 : %s   静音 : %s" % (cfg.get("volume", 0.4),
                                  "开" if cfg.get("mute") else "关"))


def list_sounds():
    cat = load_catalog()
    ids = sound_ids()
    if not ids:
        print("!! 音效目录为空: %s" % SOUNDS)
        return 1
    cur = load_config()
    for sid in ids:
        marks = []
        for ch in CHANNEL_ORDER:
            if cur.get(ch) == sid:
                marks.append(CHANNELS[ch]["title"])
        mark = ("  <- " + "/".join(marks)) if marks else ""
        print("  %-16s %s%s" % (sid, label_of(sid), mark))
    return 0


def doctor():
    """自检：settings.json 里挂的 hook 与本脚本认识的事件是否对得上。

    这是防「静默失效」的关键 —— 事件名写错时 hook 不会报错，只是不响。
    """
    problems = []
    settings = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    try:
        with open(settings, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("!! 读不到 %s: %s" % (settings, e))
        return 1

    hooks = data.get("hooks") or {}
    known = set(EVENT_TO_CHANNEL) | {"Notification"}
    found = []
    for event, groups in hooks.items():
        for grp in groups:
            for h in grp.get("hooks", []):
                cmd = h.get("command", "")
                if "soundbox.py" not in cmd:
                    continue
                # 命令形如: py -3 "…/soundbox.py" hook <event>
                tail = cmd.split("soundbox.py", 1)[1].strip()
                m = re.search(r"\bhook\s+([A-Za-z0-9_:|\-]+)", tail)
                ev = m.group(1) if m else ""
                found.append((event, grp.get("matcher", ""), ev))
                if not ev:
                    problems.append("hook %s 的命令没有 'hook <事件>' 参数: %s" % (event, cmd))
                elif ev not in known:
                    problems.append("hook %s 调用了本脚本不认识的事件 %r（将永不触发）" % (event, ev))
                if "|" in ev:
                    problems.append("hook %s 的事件名含 '|'（%r）—— cmd.exe 会当管道符，必须去掉" % (event, ev))

    if not found:
        problems.append("settings.json 里没有挂任何 soundbox hook")

    # 通道覆盖检查：每个通道至少有一个 hook 覆盖
    covered = set()
    for event, matcher, ev in found:
        if ev == "Notification":
            for ch in CHANNEL_ORDER:
                for nt in CHANNELS[ch]["notify_types"]:
                    if nt in matcher:
                        covered.add(ch)
        elif ev in EVENT_TO_CHANNEL:
            covered.add(EVENT_TO_CHANNEL[ev])
    for ch in CHANNEL_ORDER:
        if ch not in covered:
            problems.append("通道 %s (%s) 没有任何 hook 覆盖 —— 永远不会响"
                            % (ch, CHANNELS[ch]["title"]))

    # Notification 的每个 notify_type 必须真的出现在某个 matcher 里，
    # 否则脚本认识它、settings.json 却把它筛掉了 —— 这类「静默失效」doctor 要抓
    notif_matchers = " ".join(m for e, m, ev in found if ev == "Notification")
    for ch in CHANNEL_ORDER:
        for nt in CHANNELS[ch]["notify_types"]:
            if nt not in notif_matchers:
                problems.append("通知类型 %s 未出现在任何 Notification matcher 里 —— 通道 %s 缺一路触发"
                                % (nt, CHANNELS[ch]["title"]))
    # 反过来：挂了但脚本不映射的类型也会白跑，只提示不算错
    hooked_nts = set(re.findall(r"[a-z_]+", notif_matchers))
    for nt in sorted(hooked_nts - set(NOTIFY_TO_CHANNEL)):
        print("   提示: matcher 里的 %s 不映射任何通道（永远 skip）" % nt)

    print("已挂 soundbox hook:")
    for event, matcher, ev in found:
        print("  %-18s matcher=%-46s -> %s" % (event, matcher or "(全部)", ev))
    print()
    # 素材完整性
    ids = sound_ids()
    cat = load_catalog()
    missing = []
    for sid in ids:
        p = resolve(sid)
        if not os.path.isfile(p):
            missing.append(sid)
    if missing:
        problems.append("缺少音频文件: %s" % ", ".join(missing[:10]))
    if cat and len(cat) != len(ids):
        problems.append("sounds.json 有 %d 条，磁盘有 %d 个 mp3 —— 清单与素材不一致"
                        % (len(cat), len(ids)))

    # 配置有效性 + 响度检查
    cfg = load_config()
    silent = []
    for ch in CHANNEL_ORDER:
        sid = cfg.get(ch)
        path = resolve(sid)
        if not os.path.isfile(path):
            problems.append("通道 %s 配置了无效音效 %r" % (ch, sid))
            continue
        db = peak_db(path)
        if db is not None and db < PEAK_FLOOR_DB:
            silent.append("%s(%s) 峰值 %.1f dBFS" % (CHANNELS[ch]["title"], sid, db))
    if silent:
        problems.append("音效响度低于 %d dBFS，播了也听不见: %s —— 查素材源或跑 volume 重建 WAV"
                        % (PEAK_FLOOR_DB, ", ".join(silent)))

    if problems:
        print("!! 发现 %d 个问题:" % len(problems))
        for p in problems:
            print("   - %s" % p)
        return 1
    print("全部正常。")
    return 0


# ---------------------------------------------------------------------------
# 设置
# ---------------------------------------------------------------------------

def set_channel(ch, sid):
    if ch not in CHANNELS:
        print("未知通道: %s (可选: %s)" % (ch, ", ".join(CHANNEL_ORDER)))
        return 2
    if not os.path.isfile(resolve(sid)):
        print("无效音效 ID: %s" % sid)
        print("可用: %s" % ", ".join(sound_ids()[:8]) + " ...")
        return 2
    cfg = load_config()
    cfg[ch] = sid
    save_config(cfg)
    print("%s (%s) = %s  [%s]" % (ch, CHANNELS[ch]["title"], sid, label_of(sid)))
    return 0


def enable_channel(ch, val):
    if ch not in CHANNELS:
        print("未知通道: %s (可选: %s)" % (ch, ", ".join(CHANNEL_ORDER)))
        return 2
    cfg = load_config()
    cfg[ch + "Enabled"] = str(val).lower() in ("on", "1", "true", "yes")
    save_config(cfg)
    print("%s = %s" % (ch + "Enabled", cfg[ch + "Enabled"]))
    return 0


def set_volume(cfg, val):
    """改音量需重建预压 WAV（opencode 的 volume 是播放增益，不碰系统音量）。"""
    try:
        v = float(val)
    except (TypeError, ValueError):
        print("  音量需为 0..1 的数字")
        return 1
    v = max(0.0, min(1.0, v))
    cfg["volume"] = v
    save_config(cfg)
    mp = os.path.join(HERE, "make_wav.py")
    if os.path.isfile(mp):
        r = subprocess.run([sys.executable, mp, str(v)], capture_output=True, text=True)
        if r.returncode != 0:
            print("  WAV 重建失败: %s" % (r.stderr or r.stdout).strip()[:200])
            return 1
    print("  音量已设为 %.2f（WAV 已重建）" % v)
    return 0


# ---------------------------------------------------------------------------
# 交互控制台
# ---------------------------------------------------------------------------

def interactive():
    while True:
        cfg = load_config()
        print()
        print("======== Claude Code 提示音 · 音效面板 ========")
        for ch in CHANNEL_ORDER:
            meta = CHANNELS[ch]
            on, sid, lab = channel_state(cfg, ch)
            print("  %-12s %-4s %-16s %s" % (
                meta["title"], "[开]" if on else "[关]", sid, lab))
            print("               %s" % meta["desc"])
        print()
        print("  1) 试听智能体音    2) 试听权限音    3) 试听错误音")
        print("  a) 全部通道依次试听")
        print("  l) 列出全部 45 个音效")
        print("  s) 设置智能体音    p) 设置权限音    e) 设置错误音")
        print("  t) 切换通道开关    v) 设置音量")
        print("  q) 退出")
        try:
            cmd = input("选择> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if cmd == "q":
            break
        if cmd == "a":
            for ch in CHANNEL_ORDER:
                _, sid, _ = channel_state(cfg, ch)
                print("  播放 %s (%s) ..." % (sid, CHANNELS[ch]["title"]))
                play(sid)
            continue
        if cmd == "l":
            list_sounds()
            continue
        if cmd == "v":
            val = input("  音量 0..1 (当前 %s)> " % cfg.get("volume", 0.4)).strip()
            set_volume(cfg, val)
            continue
        if cmd == "t":
            print("  通道: " + ", ".join("%s=%s" % (c, "开" if cfg.get(c + "Enabled", True) else "关")
                                         for c in CHANNEL_ORDER))
            ch = input("  要切换哪个? > ").strip().lower()
            if ch not in CHANNELS:
                print("  无效通道")
                continue
            now = bool(cfg.get(ch + "Enabled", True))
            enable_channel(ch, "off" if now else "on")
            continue
        if cmd in ("1", "2", "3"):
            ch = {"1": "agent", "2": "permissions", "3": "errors"}[cmd]
            _, sid, _ = channel_state(cfg, ch)
            print("  播放 %s (%s)" % (sid, CHANNELS[ch]["title"]))
            play(sid)
            continue
        if cmd in ("s", "p", "e"):
            ch = {"s": "agent", "p": "permissions", "e": "errors"}[cmd]
            print("  当前: %s" % label_of(cfg.get(ch) or DEFAULTS[ch]))
            print("  输入音效 ID (l 看全部):")
            val = input("  音效 ID> ").strip()
            if val.lower() == "l":
                list_sounds()
                continue
            if set_channel(ch, val) == 0:
                play(val)
            continue
        print("  无效选择")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def read_payload():
    """从 stdin 读 hook 的 JSON 载荷。

    解析失败**不能静默**：否则 hook 会永远不响且无从排查。
    载荷损坏 → 写 stderr 告警，返回空 dict（仍然按无 notification_type 处理）。
    """
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception as e:
        sys.stderr.write("[soundbox] hook 载荷解析失败: %s: %s\n"
                         % (type(e).__name__, e))
        return {}


def main(argv):
    if len(argv) < 2:
        interactive()
        return 0
    cmd = argv[1]

    if cmd == "play":
        sid = argv[2] if len(argv) > 2 else "staplebops-01"
        return 0 if play(sid) else 1

    if cmd == "hook":
        event = argv[2] if len(argv) > 2 else ""
        return hook(event, read_payload())

    if cmd == "status":
        status()
        return 0

    if cmd == "doctor":
        return doctor()

    if cmd == "list":
        return list_sounds()

    if cmd == "set" and len(argv) > 3:
        return set_channel(argv[2], argv[3])

    if cmd == "enable" and len(argv) > 3:
        return enable_channel(argv[2], argv[3])

    if cmd == "mute" and len(argv) > 2:
        cfg = load_config()
        cfg["mute"] = argv[2].lower() in ("on", "1", "true", "yes")
        save_config(cfg)
        print("mute = %s" % cfg["mute"])
        return 0

    if cmd == "volume" and len(argv) > 2:
        return set_volume(load_config(), argv[2])

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
