# 挖掘流程与 opencode 进化机制

## opencode.db Schema（实测，2026-09）

```
session(id, title, directory, agent, model, tokens_input, tokens_output,
        cost, time_created, time_updated, ...)
message(id, session_id, data{role, modelID}, time_created)
part(id, message_id, session_id, data{type, text|...}, time_created)
todo(session_id, content, status, priority, position)
project(id, name, worktree)
```

- `session.directory` 区分工程脉络（同一项目跨多个会话）
- `part.data.type == "text"` 且 `message.data.role == "user"` 为用户消息
- `todo` 表是会话的任务清单——直接反映该会话干了什么
- 旧版 opencode 曾用 JSON 文件存储于 `storage/`；当前版以 SQLite 为单一事实源。脚本 `paths` 子命令会同时报告两处

## 模式信号判定标准

### 强信号（≥3 次即提议沉淀）

| 信号 | 判定方法 |
|------|---------|
| 命令链 | 多个会话的 todo/消息中出现相同顺序的命令组合（如 vet/test/build/gofmt） |
| 修复套路 | 同类故障的处置序列重复（如"改生产脚本前先备份 + grep 确认唯一匹配"） |
| 验收哲学 | 用户反复要求同一类验证（如"运行时行为 > 注释宣称"、部署后查 `/proc/<pid>/environ`） |
| 交互偏好 | 相同措辞的约束出现 3 次（如"不要乱动核心代码"、"极简白话解释"） |

### 弱信号（只记录，不主动提议）

- 单次出现的聪明操作
- 项目特定状态（API 端点、内部约定）——归 AGENTS.md，不归 skill
- 会随时间过期的技术细节（版本号、临时链接）

## 跨会话工程脉络识别

同一 `session.directory` 的多个会话构成一条工程脉络。挖掘时先按 directory 分组，脉络内的 todo 完成序列就是该工程的"工作流化石"——比单会话更有沉淀价值，因为它反映的是**跨天、跨模型的稳定模式**。

典型脉络形态（来自实测）：

```
cloudflare/          → 架构演进脉络：4+ 会话，从"理解项目"到"三池模型验收"
dmMiniPlayer/        → 硬件革新脉络：调研→选型→固件→抽象层→打包发布
Opencode/            → 基建维护脉络：存储调查→配置清理→磁盘报告
```

## opencode 进化机制（现役阵型，2026-09 部署）

对标 Hermes learning loop 的四件套已部署：

| Hermes 能力 | 现役组件 | 职责边界 |
|------------|---------|---------|
| persistent memory | `harness-memory`（全局 plugin） | 项目级 SQLite 记忆：evidence 自动捕获 → dream 固化 → 人工 review → 4 层激活注入 |
| skill 渐进披露 | `@zenobius/opencode-skillful`（全局 plugin） | `skill_find/skill_use/skill_resource` 懒加载，按需注入不占常驻 context |
| 会话考古 | 本 skill（distilling-sessions） | 挖掘 opencode.db → 模式识别 → 三流分流提议 |
| 触发规则 | `~/.config/opencode/AGENTS.md` | 沉淀触发条件 + 分流规则 + 防污染铁律 |

### 闭环数据流

```
任务 → opencode 执行 → harness-memory 自动捕获 evidence（被动层）
                ↓
        distilling-sessions 会话考古（主动层，≥3 次模式触发）
                ↓
        三流分流：丢弃 / memory:add / 炼 skill / AGENTS.md
                ↓
下一次任务 → skillful 按需加载 skill + harness-memory 4 层激活注入
```

### 防污染约束（不可违反）

- **一个记忆系统 + 一个 Skill 系统 + 一条沉淀管线**——禁止再叠加 supermemory/mnemoria/Lemma/agent-memory/short-term-memory 等同类
- harness-memory 的 dream 固化走"候选→人工 review→激活"管线，未 review 的候选不进 active memory
- skillful 懒加载 = 只有被 `skill_use` 的 skill 才消耗 token
- 升级观察期（约两周）后再评估缺口：缺短期上下文→考虑 short-term-memory；双持 Claude Code 重度使用→考虑 opencode-claude-memory；harness-memory 检索不佳→**换** Lemma/mnemoria（不是叠加）

### harness-memory 运维要点

- DB 按项目自动建于 `<project>/.harness-memory/memory.sqlite`，只读 DB 禁止写入
- 候选审查：`npx harness-memory memory:review`；批量晋升 `memory:promote --all --min-confidence 0.85`
- 记忆类型：`policy`（规则）/ `workflow`（流程）/ `pitfall`（坑）/ `architecture_constraint`（架构约束）/ `decision`（决策）
- v0.5.x 早期版本，已知短板：mock embedding 下 false positive ~29%，适合 ≤20 会话的项目；大型项目靠 distilling-sessions 的 skill 层分流减压

## 脱敏操作规范

挖掘产物落盘前，对以下模式执行 `[REDACTED]` 替换：

- `bot_token` 形态：`\d{9,10}:AA[\w-]{30,}`
- `plink ... <密码>` 形态：`plink\s+\S+\s+\S+\s+\S+`
- vless/vmess URI：`vless://[^\s]+`
- 任何 `password|token|secret|key` 后跟赋值的行——保守起见全部人工过审
