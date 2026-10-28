---
name: claude-sound-notifications
description: Claude Code 提示音：soundbox.py 三通道面板（智能体/权限/错误），对齐 opencode 音效面板
metadata:
  node_type: memory
  type: project
  modified: 2026-10-22T14:30:04.675Z
  originSessionId: 8bb7d121-167a-40ab-b13c-6fffaceab8dc
---

Claude Code（含 VSCode 扩展）没有内建音效开关（21 个配置项无 sound/audio/bell；`preferredNotifChannel=terminal_bell` 只对终端模式有效）。方案走 hooks 通道。

**主实现：`C:\Users\Admin\.claude\hooks\soundbox.py`**（Python 3.13，标准库 only，ctypes 调 winmm MCI 播音）。
模型对齐 opencode 新版「设置 → 音效」面板：**三通道**，每通道独立 enabled 开关 + 音效 ID（45 选 1）：

| 通道 | 默认音效 | 描述 | Claude Code hook |
|---|---|---|---|
| 智能体 | staplebops-01 | 当智能体完成或需要注意时播放声音 | `Stop` / `SubagentStop` / `Notification` matcher `agent_completed\|agent_needs_input` |
| 权限 | staplebops-02 | 当需要权限时播放声音 | `Notification` matcher `permission_prompt\|worker_permission_prompt` |
| 错误 | nope-03 | 发生错误时播放声音 | `StopFailure` / `PostToolUseFailure` |

配置 `hooks\soundbox.json`（`agent`/`permissions`/`errors` + 各自的 `*Enabled` + `volume`），音效清单 `hooks\sounds.json`，素材 `hooks\sounds\*.mp3`（45 个，取自 opencode 官方仓库 `packages/ui/src/assets/audio/`），`hooks\sounds\wav\*.wav` 是 ffmpeg 预降增益（0.4，对齐 opencode `attention.volume=0.4`），**play 优先用 WAV**，不改系统音量。

子命令：`status` / `list` / `play <id>` / `hook <event>` / `set <通道> <id>` / `enable <通道> on|off` / `volume <0..1>` / 无参进交互面板。

**两个已踩的坑**：
1. **命令字符串里绝不能出现 `|`** —— cmd.exe 当管道符，hook 直接失败（`'worker_permission_prompt' is not recognized...`）。matcher 里可以用 `|`，但传给脚本的是干净的 `hook Notification`，由脚本读 stdin 的 `notification_type` 自己分派。matcher 与脚本判定是**两层**。
2. **必须用 Python（`py -3`），不能用 bash** —— bash 不在 cmd/PowerShell 的 PATH，hook 会静默失败。

去抖**按事件**独立计数（`Stop` 与 `Notification:agent_completed` 同属智能体通道但互不吞）。`SOUNDBOX_TRACE=1` 可开 trace，日志在 `%TEMP%\claude-soundbox.log`。

**Why:** 用户抱怨任务完成无提示，且明确要求形状对齐 opencode 面板（命名条目 + 描述 + 事件绑定），不是自定义别名系统。

**How to apply:** 改音效先看 `hooks\README-sound.md`；改 `settings.json` 前备份到 `~/.claude/backups/`（不要在 `.claude` 根目录堆 `settings.json.bak-*`）。相关：[[opencode-config-parity]]
