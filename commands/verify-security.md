---
name: verify-security
description: "安全审查：授权边界、注入面、密钥泄露、危险函数、依赖风险。"
argument-hint: "<target-path>"
allowed-tools: Read, Grep, Glob, Bash, Edit, Write, Agent
---

读取以下技能文档，按其中的判据执行；先出结论，再给动作与验证。

```
~/.claude/skills/securing-systems/SKILL.md
```

补充上下文（纪律内核，冲突时内核优先）：

```
~/.claude/skills/_kernel/methods/SKILL.md
```