---
name: verify-quality
description: "代码质量审查：重复、复杂度、命名、死代码、可维护性。"
argument-hint: "<path-or-diff>"
allowed-tools: Read, Grep, Glob, Bash, Edit, Write, Agent
---

读取以下技能文档，按其中的判据执行；先出结论，再给动作与验证。

```
~/.claude/skills/checking-code-quality/SKILL.md
```

补充上下文（纪律内核，冲突时内核优先）：

```
~/.claude/skills/_kernel/methods/SKILL.md
```