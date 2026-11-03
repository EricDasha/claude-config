---
name: diagnosing-auto-mode-classifier
description: 当 Claude Code auto 模式连续多次拒绝工具调用并提示 classifier / auto mode 模型不可用时，立即停止任务、判定是审核器模型故障而非权限问题，并按三级回退定位与给出止损方案的诊断流程。
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash
---

# 审核器故障止损 · diagnosing-auto-mode-classifier

> 拒绝不是权限问题，是审核器那台模型死了。先止血，再换链，别硬碰。
>
> 特权工具理由：`Bash` 仅用于跑只读探针（`curl` 探本地代理、`node -e` 探上游端点、
> `ls` 检查 `settings.local.json`），不修改任何文件。写操作交给用户人工执行。

## 铁律：连续拒绝即停

同一会话内 **出现 ≥2 次"审核器无法判定"而拒绝**，立刻：

1. **停止当前任务**，不再重试同类工具调用（重试只会重复失败，烧 token）。
2. **向用户报告**，一句话定性：
   > 审核器模型 `<名字>` 当前不可用，导致 Bash / Agent 等需审核的动作被全量拒绝。这不是权限设置问题。
3. **给出止损选项**（切主模型 / 固定审核器模型 / 降权限模式），等用户选。

## 症状与鉴别

典型报错：

```
<模型名> is temporarily unavailable, so auto mode cannot determine
the safety of Bash right now. ... Note: reading files, searching code,
and other read-only operations do not require the classifier ...
```

| 特征 | 说明 |
|---|---|
| 只读可用、写入全拒 | `Read`/`Grep`/`Glob` 正常，`Bash`/`Agent`/`Edit` 被拒 |
| 报错点名模型 | 文本里出现具体模型 ID |
| `settings.local.json` 不存在 | 排除本地权限规则拦截 |

## 何时不使用

- ❌ 报错为 `Permission for this action was denied by the Claude Code auto mode classifier. Reason: …`
  → 审核器**正常判定不安全**，去改命令，不是故障。
- ❌ 报错为 `classifier denied` 并附具体理由 → 同上。
- ❌ 单次偶发拒绝后立即恢复 → 上游抖动，不触发止损协议。
- ❌ 只读工具也被拒 → 权限模式或鉴权问题，与本 skill 无关。

## 诊断流程

详细命令见 [references/probe-commands.md](references/probe-commands.md)。

1. **排除权限**：`ls ~/.claude/settings.local.json`（不存在 → 非权限问题）
2. **探本地代理**：`curl -m 6 http://127.0.0.1:15721/v1/models` — 200 且毫秒级 ⇒ 代理健康，病在上游
3. **探上游端点**：`node -e` + `fetch` + `AbortSignal.timeout` — `503/502` ⇒ **上游过载，主病因**
4. **查战绩（可选）**：cc-switch 的 `proxy_request_logs` 看该模型历史成功率

## 审核器怎么选（关键突破口）

优先级见 [references/classifier-resolution.md](references/classifier-resolution.md)：

```
1. 服务器下发  →  2. CLAUDE_CODE_AUTO_MODE_MODEL  →  3. 默认 sonnet5 系  →  4. 主模型名映射
```

**审核器可以独立于主模型固定。** 没显式配置时才会跟随主模型——这才是"主模型挂 ⇒ 审核器挂"的真因。

## 止损方案

| 序 | 方案 | 动作 |
|---|---|---|
| ① | 切回稳定主模型 | 选本地代理上**有历史 200 记录**、非免费额度的模型 |
| ② | **固定审核器（推荐）** | `settings.json` → `env` → `"CLAUDE_CODE_AUTO_MODE_MODEL": "<模型ID>"`，重启会话 |
| ③ | 降权限模式 | `/permissions` → `default` / `acceptEdits`，人工点头 |

方案 ② 硬性要求：走 **Anthropic Messages 协议**（原生或被代理翻译）、延迟低、
模型便宜够用（判定只需二元是非）。被服务器下发覆盖时日志会出现
`ignoring CLAUDE_CODE_AUTO_MODE_MODEL` —— 出现即说明第 1 级生效，env 无效。

## 收口

1. 新会话跑一条 Bash，确认不再出现 `cannot determine the safety of`
2. 若配了 env，确认调试日志**没有** `ignoring CLAUDE_CODE_AUTO_MODE_MODEL`
3. 记录所选模型与 `/v1/models` 探测延迟，作为下次故障的对照基线
