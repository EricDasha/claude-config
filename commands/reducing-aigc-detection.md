---
name: reducing-aigc-detection
description: "Systematically reduce AIGC detection rates in academic papers (Chinese/English). Analyzes detection reports, identifies high-impact sections, applies multi-layer rewriting strategies preserving formatting/footnotes, and verifies results. Supports 维普/知网/Turnitin platforms."
argument-hint: "<docx-path> [--report <pdf-path>] [--platform weipu|cnki|turnitin] [--target <percentage>]"
allowed-tools: Bash, Read, Write, Edit, Agent, WebSearch, WebFetch
---

读取以下技能文档，根据内容为用户提供专业指导：

```
~/.claude/skills/reducing-aigc-detection/SKILL.md
```
