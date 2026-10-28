---
name: cultivating-personas
description: "Distills AI agent personality patterns from conversation into a Tech Persona Card v1.0, validates the schema and voice consistency, and routes contributions through the existing submission portal. Use when the user wants to crystallize a recurring voice/tone, fork an existing persona, or share one with the community."
argument-hint: "<distill|create|validate|publish> [persona-slug]"
allowed-tools: Bash, Read, Write, Edit
---

以下所有步骤一气呵成，不要在步骤间停顿等待用户输入：

1. 读取规范：~/.claude/skills/cultivating-personas/SKILL.md
2. 执行命令：`node ~/.claude/skills/run_skill.js cultivating-personas $ARGUMENTS`
3. 按规范分析输出，完成后续动作

全程不要停顿，不要询问是否继续。
