# opencode 音效面板 → Claude Code 对照

> 数据来源：
> - opencode 源码（GitHub `anomalyco/opencode`，commit `e965774`）：
>   `packages/app/src/shell/notifications/sound.ts`、`packages/app/src/settings/general/controllers.ts`、
>   `packages/app/src/settings/model.tsx`、`packages/app/src/runtime/i18n/zh.ts`
> - 本机 `opencode.exe`（v2.1.0，Bun 单文件）二进制提取的 CLI 侧 schema
> - 本机 `claude.exe`（v2.1.306）二进制提取的 hook payload schema

## 1. opencode 新版面板的形状

`packages/app/src/settings/model.tsx` 的 `soundsSchema`：

```
sounds: {
  agentEnabled:      Boolean
  agent:             String
  permissionsEnabled: Boolean
  permissions:       String
  errorsEnabled:     Boolean
  errors:            String
}
```

默认值（`defaultSettings`）：

```js
sounds: {
  agentEnabled: true,      agent: "staplebops-01",
  permissionsEnabled: true, permissions: "staplebops-02",
  errorsEnabled: true,     errors: "nope-03",
}
```

i18n（`zh.ts`）—— 与面板逐字对应：

| key | 中文 |
|---|---|
| `settings.general.sounds.agent.title` | 智能体 |
| `settings.general.sounds.agent.description` | 当智能体完成或需要注意时播放声音 |
| `settings.general.sounds.permissions.title` | 权限 |
| `settings.general.sounds.permissions.description` | 当需要权限时播放声音 |
| `settings.general.sounds.errors.title` | 错误 |
| `settings.general.sounds.errors.description` | 发生错误时播放声音 |

事件语义（`packages/app/src/shell/notifications/notification.tsx`）：

| opencode 事件 | 触发点 | 音效 |
|---|---|---|
| 智能体 | `session.execution.succeeded` | `sounds.agent` |
| 错误 | `session.execution.failed` | `sounds.errors` |
| 权限 | 权限对话框 | `sounds.permissions` |

## 2. 音效清单（45 个）

来源 `packages/app/src/shell/notifications/sound.ts` 的 `SOUND_OPTIONS`：

```
alert-01..10      警报 01..10
bip-bop-01..10    Bip-bop 01..10
staplebops-01..07 Staplebops 01..07
nope-01..12       Nope 01..12
yup-01..06        Yup 01..06
```

素材：`packages/ui/src/assets/audio/*.mp3`（另有 `.aac`，供 web 端用）。
本机 `opencode.exe` v2.1.0 只内置 5 个（bip-bop-01/03、staplebops-06、nope-03、yup-01），
那是 CLI 侧的旧版 `attention.sounds` 机制；新版面板走的是 app 侧的完整 45 条。

## 3. Claude Code 侧的对位

Claude Code 没有「音效包」概念，但有 hook 事件，且**恰好能一一对上**。
payload schema 直接从 `claude.exe`（v2.1.306）的 Zod 定义读出，非推测：

```
Notification      { hook_event_name, message, title?, notification_type }
StopFailure       { hook_event_name, error, error_details?, last_assistant_message? }
PostToolUseFailure{ hook_event_name, tool_name, tool_input, tool_use_id, error, is_interrupt?, duration_ms? }
Stop              { hook_event_name, stop_hook_active, last_assistant_message?, background_tasks?, session_crons? }
SubagentStop      { hook_event_name, stop_hook_active, agent_id, agent_transcript_path, agent_type, ... }
```

`notification_type` 的完整枚举（`RQs`）：
```
permission_prompt, idle_prompt, auth_success, elicitation_dialog, agent_needs_input,
agent_completed, elicitation_url_dialog, worker_permission_prompt, push_notification,
computer_use_enter, computer_use_exit, quota_auto_resume_fired, quota_auto_resume_stale,
quota_auto_resume_disabled, model_refusal_fallback, auth_storage_failure, plugin_notification
```

### 映射表

| opencode 通道 | Claude Code hook | 判定依据 |
|---|---|---|
| 智能体 | `Stop` | 本轮结束 |
| 智能体 | `SubagentStop` | 子智能体结束 |
| 智能体 | `Notification` matcher `agent_completed\|agent_needs_input` | 后台智能体完成 / 等待输入 |
| 权限 | `Notification` matcher `permission_prompt\|worker_permission_prompt` | 权限对话框 |
| 错误 | `StopFailure` | API 错误结束本轮（rate_limit / overloaded / authentication_failed / … / unknown） |
| 错误 | `PostToolUseFailure` | 工具执行失败 |

matcher 语义：`rot(e)` 决定拿哪个字段去比，
`Notification`→`notification_type`、`StopFailure`→`error`、`PostToolUseFailure`→`tool_name`；
匹配用正则（`hookMatcherMatches`），所以 `a\|b` 是「或」。

### 两层过滤

**matcher 层**（settings.json，Claude Code 自己筛）和**脚本层**（soundbox.py 读 stdin 再筛）是两层，不是同一处。
`|` 必须只出现在 matcher 里 —— **命令字符串里出现 `|` 会被 cmd.exe 当管道符，hook 直接失败**。
所以脚本收到的是干净的 `hook Notification`，由脚本读 `notification_type` 自己分派。

## 4. opencode CLI 侧的旧机制（v2.1.0，仍在）

CLI/TUI 走的是另一套，与 app 侧面板无关：

```
attention: {
  notifications  : boolean      = false
  sound          : boolean      = false
  volume         : number [0,1] = 0.4
  sound_pack     : string       = "opencode.default"
  sounds         : { default, question, permission, error, done, subagent_done }
}
```

事件枚举 `LLe = ["default","question","permission","error","done","subagent_done"]`
默认表 `Kz = {default:bip-bop-01, question:bip-bop-03, permission:staplebops-06, error:nope-03, done:bip-bop-01, subagent_done:yup-01}`
覆盖语义：`[config.attention.sounds[event], Kz[event]]` 取第一个能加载的 —— 自定义优先，默认兜底。

焦点感知（CLI 独有）：`focus`/`blur` → `focused`/`blurred`/`focus_unknown`，
终端失焦时收到通知 → 切回终端时补播。VSCode 扩展无失焦检测 API，做不到。

## 5. volume 的实现方式

opencode 的 volume 是**播放时增益**，不碰系统音量。Windows 上的实测结论见
`README-sound.md` 第 7 节：唯一安全路线是 ffmpeg 预压 WAV。

## 6. 本机 opencode 的实际配置

- `~/.config/opencode/opencode.jsonc` —— **无 `attention` 段**，全部走默认
- `~/.config/opencode/cli.json` —— 只有 `theme: { name: "opencode" }`
- `~/.local/share/opencode/opencode.db` 的 `kv` 表 —— 无音效配置

**结论：本机 opencode 从未改过音效配置。**
