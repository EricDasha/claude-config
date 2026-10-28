# deploying-cloudflare-tools · 排障速查

> 本流程踩过的坑与判读。出现异常先来此卷对号。

## 镜像 / 容器

- **scratch 镜像无 shell**：`docker exec cloudflare-tools sh/ls/cfnat -h` 全部失败（无 `/bin/sh`）。要看进程与参数，用宿主上的 `docker top cloudflare-tools -o pid,args`（能看到 cfnat 完整命令行）。
- **健康闸，不是「启动了」**：`docker ps` 显示 `healthy` 只代表存活探针过；真正的发布判据是 `/api/health` 的 `gitCommit` 与本地 HEAD 相等。
- **compose env 覆盖 Dockerfile ENV**：运行时参数以 `docker-compose.yml` 的 `environment:` 为准（`${KEY:-default}` 从项目目录 `.env` 取值）。只改 Dockerfile 的 ENV、不改 compose，运行时不生效。

## 构建 / Git

- **`gitCommit` 对不上**：`build-dist.ps1` 注入构建那一刻的 `git rev-parse --short HEAD`。**先 commit 再 build**。若已 build 又 commit，重跑 `build-dist.ps1` 再传即可。
- **静默旧版（最隐蔽）**：`gitCommit` **只注入 `cloudflare-web`**（`build-dist.ps1:53`），`cfnat`/`cfdata` 用 `-ldflags=-s -w`（`:51-52`）不带版本。健康闸只查 `web`。若传输时漏推 `cfnat`/`cfdata`，`docker compose build` 会拿 NAS 上的**旧**二进制打镜像，而健康闸照样绿灯。脚本已改为无条件推全 + `sha256sum` 字节校验堵住此洞；手工链必须照抄。
- **CRLF 警告无害**：`git add` 时的 `LF will be replaced by CRLF` 是仓库 autocrlf 行为，不影响内容与构建。
- **`gofmt -l web/` 列出 `endorse.go` / `endorse_test.go`**：历史遗留，不在正常改动范围，勿顺手格式化（会污染 diff）。
- **`go test` 用 `_test.go` 同包**：`web/*_test.go` 为 `package main`；根目录 `cfnat_test.go` 带 `//go:build ignore`，需 `go test cfnat.go cfnat_test.go` 单独跑。

## 远端 shell / 工具

- **POST 用 `curl`，别用 `wget`**：本机 `wget --post-data` 对本控制台端点返回空（疑似 BusyBox wget 或引号处理），换 `curl -sS -X POST -H 'Content-Type: application/json' --data '{...}'` 立即见 HTTP 码与响应体。
- **JSON 判读用 `jq`**：NAS 已装 `jq`。避免在单行里做 `(.a|length)+(.b|length)` 这类运算——多层引号经 plink 转义后易报 `unexpected '+'`，拆成两次 `jq` 更稳。
- **plink/pscp 三枚 hostkey 全传**：`-hostkey` 可多次；漏传会触发 TOFU 交互，`-batch` 下直接失败。
- **`$env:NAS_PW`**：每会话重新注入；命令里以 `-pw $env:NAS_PW` 引用，**绝不内联明文**。

## cfnat 参数（Go flag 陷阱）

- **布尔旗标必须 `-flag=值`**：Go `flag` 对 bool 不消费后随 token，`-flag true` 会把 `true` 当位置参数并**截断其后全部解析**。历史上 `-random true` 曾导致 `-task` / `-tls` 从未生效；`web/process.go` 的 `args()` 现已统一 `-flag=值` 单参形式。
- **空字符串参数是合法 token**：`-colo ""` 在命令行里显示为空（`docker top` 看着像少了值），实为合法空值，不会吞掉下一个旗标。故 `-colo` / `-fallback` / `-priority` 的空值无问题。
- **`-sticky`**：`true`=同来源 IP 哈希到同一上游；`false`=按连接轮转铺开。由 `CFNAT_STICKY` 控制（compose 透传，默认 `true`）。

## 数据面

- **生产 `data/` 是 live**：`cfnat.log`、`cfdata.log` 等只读；任何删除/清空都是事故。
- **`/api/status.forward` 是日志尾部实况**：只在有转发发生时才有料；刚重启的 cfnat 早期为空属正常。
- **域名不可达**：优选域名走活解析，若某域名 DNS 超时（如出现 `lookup <domain>: i/o timeout`），它仍会占 `-fixed` 名额并吃掉等比例连接。`/api/cfnat/active/kick` 可手动踢（`{"ip":"<域名>"}`），但默认列表会在后续轮次把它带回来——治本需另做排除策略。
