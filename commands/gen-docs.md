---
name: gen-docs
description: "为新建模块生成文档骨架（README/API/架构决策），并检查与代码是否漂移。"
argument-hint: "<module-path>"
allowed-tools: Read, Grep, Glob, Bash, Edit, Write, Agent
---

读取以下技能文档，按其中的判据执行；先出结论，再给动作与验证。

```
~/.claude/skills/generating-docs/SKILL.md
```

补充上下文（纪律内核，冲突时内核优先）：

```
~/.claude/skills/_kernel/methods/SKILL.md
```