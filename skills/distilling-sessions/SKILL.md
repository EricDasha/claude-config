---
name: distilling-sessions
description: Mines opencode session history (SQLite opencode.db) to extract user messages, detect repeated patterns (command chains, fix rituals, acceptance checklists, interaction preferences), and distill them into new skills — an opencode-native learning loop modeled after Hermes Agent. Use when asked to summarize past sessions, inherit cross-session context, crystallize recurring workflows into skills, or review what deserves persistence. 触发词：会话总结、会话考古、历史提炼、沉淀、复盘所有会话、跨会话继承、learning loop、自动进化、类似 hermes。
user-invocable: true
allowed-tools: Read, Bash, Write, Grep
---

# distilling-sessions

> opencode 版 Hermes 学习循环：从会话历史中挖出重复 ≥3 次的模式，炼成可复用的 skill。

<!-- 扩权理由：Bash 用于运行 scripts/mine_sessions.py 挖掘 SQLite 会话库；Write/Grep 用于落盘提炼产物与查重。 -->

## 何时使用

| 场景 | 使用 | 理由 |
|------|------|------|
| 用户要求"总结会话/复盘历史/提炼经验" | ✅ | 本 skill 的主职 |
| 复杂任务收口，发现同类操作已重复 ≥3 次 | ✅ | 学习循环的核心触发 |
| 新会话需要继承旧会话工程上下文 | ✅ | 先挖掘再继承，避免凭记忆瞎编 |
| 用户问"opencode 怎么自动学习进化" | ✅ | 用本 skill + AGENTS.md 组装答案 |
| 检验既有 skill 是否覆盖了实际会话中的工作流 | ✅ | 挖掘结果可反哺 skill 改进 |

## 何时不使用

- ❌ 单次性查询"上次那个命令是啥"、当前会话刚发生且无历史重复——无粮可炼，直接 grep 数据库即可
- ❌ 提炼产物含未脱敏的 token/密码/密钥——永不落盘，先脱敏

## 铁律

1. **挖掘必脱敏**。会话历史常含用户随手粘贴的 SSH 密码、bot token、vless URI——任何落盘产物必须先 `[REDACTED]`。脚本默认只输出 user 消息文本，含敏感模式的行必须人工过审。
2. **≥3 才沉淀**。同一模式出现 3 次以上才值得炼 skill；偶尔一次的聪明操作写进当次总结即可。
3. **沉淀走 cultivating-skills 流程**。本 skill 只负责挖掘与提炼，制造 skill 的安全审查（frontmatter 合规、工具最小权限、scan）由 `cultivating-skills` 收口，不越俎代庖。
4. **只读数据库**。挖掘脚本对 `opencode.db` 只做 SELECT，永不写入。

## 主流程

```text
① 定位 → ② 挖掘 → ③ 提炼 → ④ 判定 → ⑤ 沉淀
```

### ① 定位会话库

```bash
python scripts/mine_sessions.py paths
```

默认 `~/.local/share/opencode/opencode.db`（Windows: `%USERPROFILE%\.local\share\opencode\opencode.db`）。核心表：`session`（标题/目录/token 消耗）、`message` + `part`（消息本体与部件）、`todo`（任务清单）、`project`。

### ② 挖掘

```bash
python scripts/mine_sessions.py list                # 会话清单：标题、目录、token、时间
python scripts/mine_sessions.py extract --out D.md   # 按 session 分组的 user 消息（UTF-8）
python scripts/mine_sessions.py extract --session ses_f5b6 --out D.md  # 单会话深挖
```

**乱码防御**：Windows 控制台默认 GBK，PowerShell 直接跑 Python 输出中文会乱码——一律写 UTF-8 文件再 Read。

### ③ 提炼模式

对挖掘产物做四类信号扫描，判定标准详见 [references/workflow.md](references/workflow.md)：

- **命令链**：反复出现的多步命令组合（如 vet/test/build/dist smoke/commit/push）
- **修复套路**：同类故障的固定斩法（如改生产脚本前先备份+grep 确认唯一匹配）
- **验收哲学**：用户反复要求的验证标准（如"注释宣称完成≠运行时行为完成"）
- **交互偏好**：对 agent 的行为约束（如"不要乱动核心代码"、"极简白话解释"）

### ④ 判定沉淀价值（三流分流，Memory ≠ Skill ≠ AGENTS.md）

- **丢弃**：一次性信息（临时链接、版本号、单次查询）→ 不沉淀
- **harness-memory**：用户偏好/项目事实 → `npx harness-memory memory:add --type <policy|workflow|pitfall|decision> --summary "..."`
- **skill**：稳定工作方法（命令链/修复套路/验收链）→ 提议走 `cultivating-skills` 的 distill 模式
- **AGENTS.md**：项目硬规则/强约束 → 提议写入项目 `AGENTS.md`（交互偏好→`cultivating-personas`，仅 Claude 侧）

### ⑤ 沉淀

提议格式（用户点头前不落盘）：

```
【沉淀机会】<观察到的模式，附 ≥3 次证据的会话 ID>
建议路径：<cultivating-skills | cultivating-personas | AGENTS.md>
是否炼制？(y / 调整 / 跳过)
```

## 与其他 skill 联动

- **cultivating-skills**：制造流程与安全审查，本 skill 的下游
- **cultivating-personas**（交互偏好信号）· **git-master**（沉淀产物入 git 时的原子提交规范）

## 收口

- 脚本跑通、产物 UTF-8 可读、敏感信息已 `[REDACTED]`
- 每个提议沉淀的模式附 ≥3 次的会话 ID 证据
- 用户点头后才落盘，落盘后跑 `skill_forge.js lint + scan`
