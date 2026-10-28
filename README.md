# Claude Code 个人配置备份

本仓库是 `C:\Users\Admin\.claude\` 的配置快照，用于灾难恢复。**不是可直接运行的安装包**，恢复时需要按下面的路径放回。

最后更新：2026-10-29

## 目录结构

| 仓库路径 | 应放回的位置 | 内容 |
|---|---|---|
| `CLAUDE.md` | `~/.claude/CLAUDE.md` | 全局指令（人格、规则、技能路由） |
| `settings.json` | `~/.claude/settings.json` | 主配置：env、permissions、hooks、modelPicker |
| `output-styles/` | `~/.claude/output-styles/` | 输出风格（当前用 `abyss-cultivator`） |
| `commands/` | `~/.claude/commands/` | 自定义斜杠命令 |
| `skills/` | `~/.claude/skills/` | 全部技能（40+，含 `_kernel` 决策内核） |
| `hooks/` | `~/.claude/hooks/` | 钩子脚本 + 音效库（47 个 mp3） |
| `memory/` | `~/.claude/projects/<项目>/memory/` | 跨会话记忆 |
| `jevvy/jevvy.jsonc` | `~/.config/jevvy/jevvy.jsonc` | 权限门禁配置 |

## 恢复步骤

```bash
# 1. 克隆
git clone https://github.com/EricDasha/claude-config.git ~/claude-config

# 2. 放回配置（先备份现有的）
cp -r ~/claude-config/{CLAUDE.md,settings.json,output-styles,commands,skills,hooks} ~/.claude/
cp -r ~/claude-config/memory/. ~/.claude/projects/<你的项目>/memory/

# 3. jevvy 配置：先还原 key
mkdir -p ~/.config/jevvy
cp ~/claude-config/jevvy/jevvy.jsonc ~/.config/jevvy/
# 把 <YOUR_OPENROUTER_KEY> 换成真实 key

# 4. jevvy 本体需要另装
npm install -g @jevvy/permissions@0.8.0
```

## 密钥处理

**仓库内不含任何真实密钥。** 已做以下处理：

- `settings.json` 的 `ANTHROPIC_AUTH_TOKEN` 是 `PROXY_MANAGED` 占位符（由 cc-switch 路由服务注入真 key）
- `jevvy/jevvy.jsonc` 的 `apiKey` 替换为 `<YOUR_OPENROUTER_KEY>`
- 已全库扫描，无 `sk-` / `ak-` / `gho_` 前缀的真实凭据

**注意**：`settings.json` 的 `permissions.allow` 里有一条历史命令含字面量 `"OPENROUTER_API_KEY=badkey"`，那是当时测试用的无效值，不是真 key。

## 关键配置说明

### 模型链路

本机走 cc-switch 的 routing 模式：

```
Claude Code → 127.0.0.1:15721 (cc-switch) → 真实 provider
```

- `ANTHROPIC_BASE_URL` 固定指向本地路由
- 真实 provider 配置在 **`G:\EricDasha.github.io\.cc-switch\cc-switch.db`**，不是 `C:\Users\Admin\.cc-switch\`（那边只有 Claude Official）
- 详细见 `memory/claude-code-model-routing.md`

### 审查器选型

`CLAUDE_CODE_AUTO_MODE_MODEL` 指向的模型挂掉会导致**所有工具调用被拦**。实测结论：

| 模型 | 得分 | 备注 |
|---|---|---|
| `doubao-seed-2-1` | **4/4** | 当前在用，最快的 1.4s |
| `big-pickle` | 4/4 | 可用 |
| `spark-x2.6-4b` | 3/8 失败 | 思考块吃掉 64 token，不可用 |
| `gpt-free` / `gpt-image-2` | 0/4 | **整齐答反**，最危险 |
| `glm-5.3-flash` | 0/4 | 502 |

### jevvy 权限门禁

挂在 `PermissionRequest` 钩子，用 `typesafe/jev-1.14`（决策模型）判断命令是否放行。**只放不拦**——超时或出错都回落到人工弹窗。

注意 jev 是 decisions 模型，**不能**当聊天模型或自动模式审查器（协议不兼容，直接 400）。

## 与本仓库配合的技能

- `skills/gating-permissions-with-jev/` — jevvy 安装与排障
- `skills/managing-cc-switch/` — cc-switch 三种模式、`live-state.json` 字段、三个配置冲突点
- `skills/searching-files-with-everything/` — 用 Everything 的 es.exe 快速定位文件
