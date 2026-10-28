# deploying-cloudflare-tools · 远端坐标

> 本卷只记「发布目标在哪」，不含任何口令。口令永远走运行时环境变量 `$env:NAS_PW`。

## 本机（构建侧）

| 项 | 值 |
|----|----|
| 仓库根 | `G:\EricDasha.github.io\cloudflare` |
| 构建脚本 | `<repo>\scripts\build-dist.ps1`（linux/amd64，ldflags 注入 `main.gitCommit` / `main.buildTime`） |
| 产物目录 | `<repo>\dist\linux-amd64\`（`cloudflare-web` / `cfnat` / `cfdata` / `sing-box`）+ `<repo>\dist\ca-certificates.crt` |
| 远端工具 | `C:\Program Files\PuTTY\plink.exe`、`C:\Program Files\PuTTY\pscp.exe` |

## 生产主机（NS）

| 项 | 值 |
|----|----|
| 主机 | `192.168.1.50`（LAN 私网，务必以 `$env:NAS_HOST` 覆盖） |
| 用户 | `administer`（`$env:NAS_USER` 可覆盖） |
| 部署根 | `/vol1/1000/Docker/CFNat`（`$env:NAS_ROOT` 可覆盖） |
| 产物落点 | `<NAS_ROOT>/dist/linux-amd64/`、`<NAS_ROOT>/dist/ca-certificates.crt` |
| compose | `<NAS_ROOT>/docker-compose.yml`（服务 `cloudflare-tools`，镜像 `local/cloudflare-tools:latest`） |
| 容器名 | `cloudflare-tools` |
| 端口 | `8080`（控制台）、`1234`（cfnat 转发入口） |
| 健康端点 | `http://192.168.1.50:8080/api/health` |

## SSH 主机指纹（PuTTY `-hostkey`，公钥，非机密）

```
49:73:6a:00:92:6f:f7:f8:93:7a:9d:aa:10:3e:53:2a
ed:dc:9b:75:cf:e9:53:c9:99:ed:ca:1f:49:98:df:15
e6:6b:ff:1d:08:02:34:70:bc:c2:33:e1:64:8d:10:3c
```

三枚对应不同算法；调用 `plink` / `pscp` 时**全部**传给 `-hostkey`，免 TOFU 交互。

## 口令注入（唯一正确姿势）

```powershell
$env:NAS_PW = '<从你的密码管理器取>'
# 或一次性：$env:NAS_PW = Read-Host -AsSecureString | ConvertFrom-SecureString -AsPlainText  # 视版本
```

**绝不允许**：把口令写进 skill、`.env`、命令历史、仓库、聊天记录。
调用示例（单次会话内有效）：

```powershell
& $env:PLINK -batch -hostkey <hk1> -hostkey <hk2> -hostkey <hk3> -pw $env:NAS_PW administer@192.168.1.50 "<远端命令>"
```

## 生产红线（永不由本流程触碰）

- `/vol1/1000/Docker/CFNat/data/`——live 账本与日志（`cfnat.log`、`cfdata.log`、优选设置、订阅缓存）。**只读，绝不删改**。
- 现役容器 `/proc` 之外的宿主状态：不动其它容器（`sing-box`、`cli-proxy-api`、`microsoft-rewards-script`）。
- 回滚锚点 `*.bak-<stamp>` 至少保留最近一次，覆盖前不得删除。
