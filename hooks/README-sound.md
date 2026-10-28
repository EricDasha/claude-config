# Claude Code 提示音 — 怎么测 / 怎么改

## 0. 面板模型

对齐 opencode「设置 → 音效」面板（`packages/app/src/settings/general/controllers.ts`）：

| 通道 | opencode 键 | 默认音效 | 描述 |
|---|---|---|---|
| 智能体 | `sounds.agent` | `staplebops-01` | 当智能体完成或需要注意时播放声音 |
| 权限 | `sounds.permissions` | `staplebops-02` | 当需要权限时播放声音 |
| 错误 | `sounds.errors` | `nope-03` | 发生错误时播放声音 |

每通道独立：`enabled` 开关 + 音效 ID（45 选 1）。
配置在 `~/.claude/hooks/soundbox.json`，音效清单在 `~/.claude/hooks/sounds.json`。

## 1. VSCode 扩展没有内建音效

扩展 21 个配置项里没有任何 sound/audio/bell；`preferredNotifChannel=terminal_bell` 只对终端模式有效。
所以提示音走 **hooks** 通道：Claude 触发事件 → 跑一个命令 → 命令播音。

## 2. 交互式控制台（推荐）

```powershell
py -3 "$HOME\.claude\hooks\soundbox.py"
```

| 键 | 作用 |
|---|---|
| `1` `2` `3` | 试听智能体 / 权限 / 错误 音 |
| `a` | 三个通道依次试听 |
| `l` | 列出全部 45 个音效（标 `<-` 的是当前绑定） |
| `s` `p` `e` | 设置智能体 / 权限 / 错误 音（输入 ID，存前会播一次） |
| `t` | 切换某通道开关 |
| `v` | 改音量（会重建 WAV） |
| `q` | 退出 |

## 3. 命令行

```powershell
py -3 "$HOME\.claude\hooks\soundbox.py" status                # 当前配置
py -3 "$HOME\.claude\hooks\soundbox.py" doctor                # 自检（改配置后必跑）
py -3 "$HOME\.claude\hooks\soundbox.py" list                  # 45 个音效
py -3 "$HOME\.claude\hooks\soundbox.py" play staplebops-01    # 播一次
py -3 "$HOME\.claude\hooks\soundbox.py" set agent nope-05     # 设智能体音
py -3 "$HOME\.claude\hooks\soundbox.py" enable errors off     # 关错误音
py -3 "$HOME\.claude\hooks\soundbox.py" volume 0.5            # 改音量
```

> ⚠️ 别用 `bash`。这台机器上 `bash` 只在 Git Bash 里，cmd / PowerShell 都不认。

## 4. 挂载的 hook（settings.json）

| hook 事件 | matcher | 通道 | 命令 |
|---|---|---|---|
| `Stop` | — | 智能体 | `hook Stop`（脚本内判「真的停下」，见下） |
| `Notification` | `agent_completed\|agent_needs_input\|idle_prompt` | 智能体 | `hook Notification` |
| `Notification` | `permission_prompt\|worker_permission_prompt\|elicitation_dialog\|elicitation_url_dialog` | 权限 | `hook Notification` |
| `StopFailure` | — | 错误 | `hook StopFailure` |
| `PostToolUseFailure` | — | 错误 | `hook PostToolUseFailure` |

**两个坑（都踩过）**：

1. **命令里不能出现 `|`** —— cmd.exe 会把它当管道符，hook 直接失败
   （`'worker_permission_prompt' is not recognized as an internal or external command`）。
   所以 matcher 里用 `|`，但传给脚本的是干净的 `hook Notification`，由脚本读 stdin
   的 `notification_type` 自己分派。matcher 与脚本判定是两层，不是同一处。
2. **必须用 Python** —— `py -3` 在 cmd 和 PowerShell 都在 PATH，bash 不在。

## 4.5 什么情况下**不**响（2026-10-27 修）

提示音唯一的职责是「Agent 在后台干活、需要你介入时叫你」。以下事件虽触发 hook，但脚本主动吞掉：

| 事件 | 不响的条件 | 为什么不响 |
|---|---|---|
| `Stop` | `background_tasks` 非空 | 会话只是被挂起等后台任务唤醒，还没完 |
| `Stop` | `session_crons` 非空 | 还有 cron / ScheduleWakeup / loop 会叫醒它 |
| `Stop` | `notification_type` 属 `agent_*` / `idle_prompt` | 父代理替子代理收尾，不是你的事 |
| `Stop` | payload 带 `agent_id` / `parent_tool_use_id` | 同上 |
| `SubagentStop` | 一律不挂 | 子智能体结束 ≠ 需要你介入；这是最主要的乱响来源 |
| `StopFailure` | `error` 为 `aborted` 等 | 你按了 Esc，不是出错 |
| `PostToolUseFailure` | `is_interrupt: true` | 同上 |

后台智能体**真正**完成时，由 `Notification:agent_completed` 接棒响 `Staplebops 01`。

## 5. 端到端真验

1. `Ctrl+Shift+P` → `Developer: Reload Window`（settings.json 在会话启动时读，不重载吃不到新 hook）
2. 跑一条会触发权限确认的命令 → 应响 `Staplebops 02`
3. 让本轮跑完 → 应响 `Staplebops 01`
4. 跑一条后台任务（`run_in_background`）期间回合暂停 → **不应响**

### 主动诱发（不靠等，直接打 hook）

```bash
cd ~/.claude/hooks
py -3 soundbox.py hook Notification <<< '{"notification_type":"permission_prompt"}'   # 应响 Staplebops 02
py -3 soundbox.py hook Notification <<< '{"notification_type":"agent_completed"}'     # 应响 Staplebops 01
py -3 soundbox.py hook StopFailure  <<< '{"error":"rate_limit"}'                      # 应响 Nope 03
py -3 soundbox.py hook Stop         <<< '{"background_tasks":[{"id":"x"}]}'           # 应静默
```

每条都要间隔 >2s，否则同键事件会被去抖吞掉（`skip 去抖抑制` 是正常现象）。

### 响度

`doctor` 会量每个已绑定音效的峰值电平，低于 -40 dBFS 判为「播了也听不见」。
素材来自 opencode 官方音频，本身就是小声的；`volume=0.4` 后峰值约 -24 dBFS。
若嫌太小，`py -3 soundbox.py volume 1.0` 重建即可（不碰系统音量）。

## 6. 排查

```powershell
# a) 自检：事件名漂移 / 通道没覆盖 / 素材缺失 / 配置无效 —— 一次全查
py -3 "$HOME\.claude\hooks\soundbox.py" doctor

# b) 手动跑 hook 命令，看有没有报错
'{"notification_type":"permission_prompt"}' | py -3 "$HOME\.claude\hooks\soundbox.py" hook Notification

# c) 看 trace，确认事件到底归到了哪个通道（默认已开启）
Get-Content "$env:TEMP\claude-soundbox.log" -Tail 30
$env:SOUNDBOX_TRACE = "0"   # 需要时关闭
```

`doctor` 存在的意义：**hook 事件名写错时不会报错，只是不响**。
它会检查 settings.json 里的事件名是否是本脚本认识的、是否含 `|`（cmd 管道符坑）、
三个通道是否都有 hook 覆盖、45 个素材是否齐、配置里的音效 ID 是否有效。

trace 输出形如：
```
22:26:13 play     Stop                    agent -> staplebops-01 (Staplebops 01)
22:26:13 play     Notification             permissions -> staplebops-02 (Staplebops 02)
22:26:13 skip     Notification             去抖抑制 (Notification:permissions)
22:26:13 skip     Notification             notification_type=idle_prompt 不映射任何通道
```

`skip` 是正常的（去抖 / 该通知类型本来就不映射到任何通道）。

## 7. 音量

opencode 的 `attention.volume` 是**播放时增益**（0..1），不碰系统音量。
Windows 上的实现障碍与解法（全部实测）：

| 方案 | 结果 |
|---|---|
| MCI `SET alias VOLUME TO n` | ❌ rc=259，mpegvideo 设备不支持 |
| `waveOutSetVolume(WAVE_MAPPER)` | ❌ 污染系统音量且**不可逆还原**，已弃用 |
| `IAudioEndpointVolume` (COM) | ❌ `CoCreateInstance` hr=0x800401f0 |
| WMP `MediaPlayer` COM | ❌ hr=0x80040154，类未注册 |
| `PlaySound` | ❌ 只支持 WAV，不支持 MP3；无音量参数 |
| **ffmpeg 预压 WAV** | ✅ **采用**：`-af volume=0.4` 生成 `sounds\wav\*.wav` |

改音量要重建 WAV（`make_wav.py`），已封装进控制台的 `v` 键与 `volume` 子命令。
ffmpeg 路径候选：`E:\Program Files\FFmpegFreeUI\ffmpeg.exe`（full build）。

## 8. 已知边界

- 扩展需重载窗口 / 新开会话才读新配置
- Windows 系统总音量或输出设备静音时，MCI 仍返回成功但听不到 —— 去查系统音量，不是本工具的锅
- 去抖**按事件**独立计数：`Stop` 与 `Notification:agent_completed` 同属智能体通道但互不吞
- opencode 有「终端失焦时补播」，VSCode 扩展无失焦检测 API，做不到
- 音效素材来自 opencode 官方仓库 `packages/ui/src/assets/audio/*.mp3`（45 个，含 aac/mp3 两套，we 只取 mp3）
