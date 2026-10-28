---
name: managing-cc-switch
description: CC Switch（farion1231/cc-switch）是管理 Claude Code、Codex、OpenCode、Gemini CLI、Grok Build、OpenClaw、Hermes 等多家 AI agent 的 provider、MCP servers、Skills 的中枢与事实源。当需要查看/修改这些 agent 的 MCP、provider、skill 配置，或遇到「改了配置文件却不生效」「MCP 反复失效」「skill 重复且版本漂移」「provider 被莫名切回」「agent 的设置和 cc-switch 抢着改 settings.json」「自动模式审查器突然不可用」时使用。关键词：cc-switch、ccswitch、MCP 不生效、provider 切换、skill 同步、接管优先级、live-state.json、routing 模式、aggregation 聚合、PROXY_MANAGED、contract、exclusive。
---

# 管理 CC Switch

## 一句话铁律
**CC Switch 是权威源（source of truth）。** 它管辖的字段（provider / MCP / skill）会自动同步、**覆盖**各 agent 自己的配置文件。**直接改 agent 的 `opencode.json` / `opencode.jsonc` 无效——凡被它接管的字段，必须改 CC Switch 本身。**

## 它是谁
- GitHub：`farion1231/cc-switch` ｜ 官网 ccswitch.io ｜ Tauri/Rust 桌面应用（MIT）
- 统一管理：Claude Code、Claude Desktop、Codex、Gemini CLI、Grok Build、**OpenCode**、OpenClaw、Hermes Agent、Pi、MiniMax Code、Kimi Code

## 数据位置
- 默认目录：`%USERPROFILE%\.cc-switch\`
- **当前生效目录以日志为准**——启动时日志打印 `使用 Store 中的 app_config_dir: <path>`（可能不是默认位置）
- 核心库：`cc-switch.db`（SQLite）。关键表：
  | 表 | 内容 |
  |---|---|
  | `mcp_servers` | MCP 定义。`server_config` 为 JSON；`enabled_<agent>` 为各 agent 开关 |
  | `providers` | 各 agent 的 provider（`app_type` 区分 claude/codex/opencode/...） |
  | `skills` / `skill_repos` | skill 管理与来源仓库 |
  | `settings` | `common_config_<agent>` 等公共配置片段 |
- **设备状态**：`live-state.json`——记录每个 agent 当前处于 direct / routing / aggregation 哪种模式、挂了哪个 provider、写入了什么。**这是排查"为什么流量去了某家"的第一现场。**
- **安全**：db 内**明文**存有 API key、OAuth token、账号邮箱。**切勿放入 git 仓库或云同步目录**。

## 三种连接模式（v4.0+）
每个 agent 只能同时处于一种模式：

| 模式 | 请求路径 | 配置里看到什么 | 能否故障转移 |
|---|---|---|---|
| **Direct** 直连 | 客户端 → provider | 真实 `ANTHROPIC_BASE_URL` | 否 |
| **Routing** 路由 | 客户端 → `http://127.0.0.1:15721` → provider | `ANTHROPIC_BASE_URL=http://127.0.0.1:15721`，key 为 `PROXY_MANAGED` | **是**，按队列轮转 |
| **Aggregation** 聚合 | 同上，但按 `/model` 选的模型分发 | 模型名带 `ccs-` 前缀 | 否 |

**cc-switch 必须保持运行**，退出会写回 direct 配置，下次启动重连。

### Routing 模式到底怎么写配置
官方文档明说：**只改关键字段，其余不动**。

```json
// 进入 routing 前
{ "env": { "ANTHROPIC_BASE_URL": "https://api.anthropic.com" } }
// 进入 routing 后
{ "env": { "ANTHROPIC_BASE_URL": "http://127.0.0.1:15721" } }
```

同时真实 key 被替换成占位符 `PROXY_MANAGED`。**你写在 `settings.json` 的 `model`、hooks、permissions、outputStyle 等，它一概不碰。**

### live-state.json 里的字段含义
```jsonc
{
  "apps": {
    "claude": {
      "mode": "proxy",                    // 等价于 routing
      "attached": true,
      "proxy_route": "<provider 名>",      // 当前路由到谁
      "contract": {
        "exclusive": {                     // cc-switch 要求独占的键
          "CLAUDE_CODE_AUTO_MODE_SERVER": "0"
        }
      },
      "stack": {
        "enabled": true,
        "members": ["<provider-id>", ...], // 故障转移队列，顺序即优先级 P1→Pn
        "keys": { "<别名>": "<provider-id>" }
      }
    }
  }
}
```
- `members` 的顺序就是优先级：P1 失败 4~8 次（Claude 默认阈值较宽松）才切 P2。
- `keys` 里的别名对应 `ccs-claude-<别名>--<模型名>` 模型串里的那个 `<别名>`。

## 和 agent 设置"抢权限"的三个真实冲突点

### 1. `model` 字段指向的 provider 不在 routing 队列里 / 不可用
现象：`/model` 切了但很快弹回原样；或请求全超时。
原因：routing 模式下 provider 由 cc-switch 决定，`model` 里的前缀只是选择模型，不代表能通。
处理：模型名必须对应 `live-state.json` 的 `stack.keys` 里存在的别名。

### 2. `CLAUDE_CODE_AUTO_MODE_MODEL` 与 `contract.exclusive` 打架
现象：`AUTO_MODE_MODEL` 指向某个中转模型，但该中转不转发、或该模型本身超时 → 报 `xxx is temporarily unavailable, so auto mode cannot determine the safety of ...`，所有 Bash 调用被拦（fail-closed）。
原因：自动模式要用**独立的**分类请求调 `AUTO_MODE_MODEL`；这条请求同样走 `ANTHROPIC_BASE_URL`，被 cc-switch 路由。`contract.exclusive` 只保证 `CLAUDE_CODE_AUTO_MODE_SERVER=0` 这一个键不被写，**不保证模型可用**。
处理：`CLAUDE_CODE_AUTO_MODE_MODEL` 要指向路由链路上**真实可用、响应够快**的聊天模型（能按提示吐 `<block>yes|no</block>` 的那种），不要用 4B 级小模型或 decisions 类模型。

### 3. 退出 routing 时的写回覆盖
现象：手动修好的 `ANTHROPIC_BASE_URL` / key，重启 cc-switch 后又变了。
原因：cc-switch 退出时按"direct provider"重写配置，不读你手改的内容（官方明说不依赖进入时的备份）。
处理：要么在 cc-switch GUI 里改 direct provider，要么先在 GUI 里 "Back to direct" 再手改。

## 接管优先级（高 → 低）
```
CC Switch db  ──同步写入──►  agent 配置文件（opencode.jsonc 等）  ──►  agent 运行时
                                                                       ▲
用户手改 agent 配置文件（最低，必被覆盖）──────────────────────────────┘
```
**但注意**：routing 模式只管 `ANTHROPIC_BASE_URL` 和 key 两个字段。`model`、`env` 里的其他键、hooks、permissions 都归用户，cc-switch 不覆盖。别把两者混为一谈。

## 修改配置的正确姿势
1. **首选：在 CC Switch GUI 里改**——它下次同步即写回 agent 配置，一劳永逸。
2. 次选（GUI 不便时）：**先退出 CC Switch 进程** → 改 `cc-switch.db` → 重启 CC Switch 触发同步。**必须在进程停止时改，否则被其内存值覆盖回去。**
3. 只改 agent 配置文件里**未被接管**的字段（model / hooks / permissions）→ 直接改有效。
4. 改被接管的字段（BASE_URL / key / MCP / skill）→ 必须走 1 或 2。

## 常见坑
- 改 `opencode.json` / `opencode.jsonc` 的 MCP / provider 不生效 → 被 CC Switch 覆盖。
- 工具目录搬家（如 `C:\tools` → `G:\tools`）→ 必须在 CC Switch 里同步改路径。
- MCP 带 `CHROME_PATH` 等环境变量 → 可能导致启动挂起（例：hugin 的 `warmBrowser()` 调 `puppeteer.launch()` 无超时，Edge 不回 CDP 时阻塞在 MCP 握手前）。
- 同一 skill 出现在多处（`.config/opencode/skills`、`.claude/skills`、CC Switch 主库）且内容分叉 → 加载版本漂移；CC Switch 的 `skillSyncMethod` 为 `symlink` 时新 skill 建符号链接，旧 skill 可能是实体副本。
- CC Switch 可能存在**双数据目录**（默认位置 + app_config_dir），排查时两者都要看。**两边的 `live-state.json` 可能完全不同**——一个说 direct，一个说 proxy。
- 用户手写在 agent 配置里、但**未登记进 CC Switch db 的 MCP**，CC Switch 看不到也不管（游离态）。
- 聚合模式（Aggregation）下**没有故障转移**；切回 Routing 后队列配置才重新生效。

## 排障流程
1. 现象为「改了不生效」→ 先判断该字段是否被 CC Switch 接管。
2. 读 `live-state.json` 确认当前模式与实际路由目标。
3. 定位生效目录：看最新日志的 `app_config_dir`。
4. 查 db 对应表的当前值（可用 node + better-sqlite3 只读打开）。
5. 改 CC Switch（GUI 优先，或停进程改 db），而非只改 agent 文件。
6. 验证：`opencode mcp list` 或对应 agent 的检查命令应显示目标状态。

## 快速只读检查（不启动 GUI）
```powershell
# 生效目录
Get-Content <app_config_dir>\logs\cc-switch.log -Tail 30
# 当前模式与路由目标
Get-Content <app_config_dir>\live-state.json -Raw
# db 内容（需 better-sqlite3）
node -e "const D=require('<path>/better-sqlite3');const db=new D('<app_config_dir>/cc-switch.db',{readonly:true});console.log(db.prepare('SELECT id,server_config,enabled_opencode FROM mcp_servers').all())"
```

## 参考
- 官方手册：`docs/user-manual/en/4-proxy/4.2-routing.md`（路由）、`4.3-failover.md`（故障转移）、`4.6-aggregation.md`（聚合）
