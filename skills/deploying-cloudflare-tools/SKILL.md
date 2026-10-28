---
name: deploying-cloudflare-tools
description: 把本地改好的 cloudflare-tools 产物安全发布到远程 Docker 主机（NAS）并证其上线——冻结提交→构建 linux/amd64→验二进制标记→备份锚点→pscp 传输→重建容器→健康闸→可选回滚。当 web/ 或根目录 cfnat.go / cfdata.go 需要上线、或线上要退到上一版时使用。
user-invocable: true
argument-hint: [deploy | rollback | verify]
allowed-tools: Read, Bash
---

# deploying-cloudflare-tools

> 本项目从本地工作区到生产 NAS 的唯一发布通道：先证后发，留锚可退。

## 何时使用 / 何时不使用

| 场景 | 使用 | 理由 |
|------|------|------|
| `web/`、`cfnat.go`、`cfdata.go` 改动要上线 | ✅ | 全链带标记校验与回滚锚点 |
| 线上版本异常，要退回上一版 | ✅ | 有 `*.bak-<stamp>` 锚点可反演 |
| 只跑单测 / 静态检查，不发布 | ❌ | 用 `automating-devops`，本地命令即可 |
| 触碰生产 `data/`（live 账本 / 日志） | ❌ | 命根子，绝不由本流程动 |

## 前置

- Windows + PowerShell 7；工具链 `go` / `node` / `pwsh`、远端 `docker`、PuTTY（plink/pscp）。
- NAS 口令走**运行时环境变量 `$env:NAS_PW`**——skill 与任何仓库永不落盘。
- 远端坐标（host / user / 路径 / 三枚 hostkey）：见 [references/targets.md](references/targets.md)。

## 主流程（七步）

1. **冻结**：工作树干净、改动已 commit——`build-dist.ps1` 把 HEAD 短哈希注入二进制，健康闸据此比对。
2. **自检**：`go build ./... && go vet ./... && go test ./...`；动过前端再加 `node --check web/static/app.js`。
3. **构建**：`pwsh -File scripts/build-dist.ps1`（linux/amd64，含 sing-box，按 stamp 缓存）。
4. **验标记**：`[IO.File]::ReadAllText('dist\linux-amd64\cloudflare-web',[Text.Encoding]::Latin1).Contains(<HEAD 短哈希>)` 须为真。
5. **备份 + 传输 + 字节校验**：远端先 `cp -p` 生成 `cloudflare-web.bak-<stamp>` 等锚点，再 `pscp` **无条件**推 6 件（`cloudflare-web`/`cfnat`/`cfdata`/`ca-certificates.crt`/compose/Dockerfile），并对前四件做 `sha256sum` 与本地比对。
   > 为何要校验：`gitCommit` 只注入在 `web`，`cfnat`/`cfdata` 无版本可查；漏推会被健康闸绿灯放行成「静默旧版」。
6. **重建**：远端 `docker compose build && docker compose up -d`。
7. **健康闸**：`/api/health` 的 `gitCommit == 本地 HEAD` 且容器 `healthy`；再按改动内容做功能级验证。

> 完整命令链与逐条判读：[references/workflow.md](references/workflow.md)。
> 一步到位脚本：`pwsh <skill>/scripts/deploy.ps1 [-Msg "<提交信息>"] [-Push] [-Rollback] [-Verify] [-DryRun]`
> （`-Verify` 只读体检；`-DryRun` 只跑本地四步不碰远端；三态均已实测通过）。

## 为何需要 Bash

七步全是外部进程（go / pwsh / pscp / plink / docker over ssh）。Bash 仅执行上述命令；
**破坏性动作（删 `data/`、force push、跨主机 rm）不在流程内**——红线见参考卷。

## 与其他 skill 联动

- `shipping-changes`：上层「想法→PR」编排脊柱；本 skill 是其「落地到这台 NAS」的具体段。
- `automating-devops`：Git / CI 知识库；本 skill 走**无 CI 的手工发布**通道。

## 收口

- `/api/health.gitCommit == 本地 HEAD` 且容器 healthy。
- 改动对应的线上证据（API 字段存在 / UI 元素渲染 / 行为符合预期）已取得。
- 回滚锚点存在；失败即还原 `.bak` 二进制与 compose 后 `up -d`。
- 常见坑（scratch 无 shell、`docker top` 看参数、curl≠wget）：[references/troubleshooting.md](references/troubleshooting.md)。
