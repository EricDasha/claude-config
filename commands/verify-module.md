---
name: verify-module
description: "校验模块完整性：入口、边界、错误路径、测试覆盖、与声明是否一致。"
argument-hint: "<module-path>"
allowed-tools: Read, Grep, Glob, Bash, Edit, Write, Agent
---

读取以下技能文档，按其中的判据执行；先出结论，再给动作与验证。

```
~/.claude/skills/verifying-modules/SKILL.md
```

补充上下文（纪律内核，冲突时内核优先）：

```
~/.claude/skills/_kernel/methods/SKILL.md
```