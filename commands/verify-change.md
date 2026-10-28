---
name: verify-change
description: "大改动回归面审查：影响范围、兼容性、隐性副作用、遗漏调用点。"
argument-hint: "<diff-or-branch>"
allowed-tools: Read, Grep, Glob, Bash, Edit, Write, Agent
---

读取以下技能文档，按其中的判据执行；先出结论，再给动作与验证。

```
~/.claude/skills/analyzing-changes/SKILL.md
```

补充上下文（纪律内核，冲突时内核优先）：

```
~/.claude/skills/_kernel/methods/SKILL.md
```