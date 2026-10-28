---
name: cultivating-skills
description: "Distills repeated workflows into reusable skills, improves existing skills, and gates them through a three-tier publish funnel (local → project → community). Use when the agent or user notices a pattern worth crystallizing, when an existing skill is incomplete, or when something deserves community contribution. Default deny on dangerous tools and side effects."
argument-hint: "<distill|create|improve|publish> [topic-or-path]"
allowed-tools: Bash, Read, Write, Edit, Grep
---

以下所有步骤一气呵成，不要在步骤间停顿等待用户输入：

1. 读取规范：~/.claude/skills/cultivating-skills/SKILL.md
2. 执行命令：`node ~/.claude/skills/run_skill.js cultivating-skills $ARGUMENTS`
3. 按规范分析输出，完成后续动作

全程不要停顿，不要询问是否继续。
