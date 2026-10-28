# deploying-cloudflare-tools · 工作流

> **一键**：`pwsh <skill>\scripts\deploy.ps1 [-Msg "<提交信息>"] [-Push] [-Rollback] [-Verify] [-DryRun]`
> —— 本卷是它展开的手工链，供排查与核对；七步顺序与远端命令与脚本完全一致，均经实测。
>
> 变量先备，再按步执行。

## 变量预备（PowerShell）

```powershell
$Repo   = 'G:\EricDasha.github.io\cloudflare'
$Plink  = 'C:\Program Files\PuTTY\plink.exe'
$Pscp   = 'C:\Program Files\PuTTY\pscp.exe'
$Host   = $env:NAS_HOST ?? '192.168.1.50'
$User   = $env:NAS_USER ?? 'administer'
$Root   = $env:NAS_ROOT ?? '/vol1/1000/Docker/CFNat'
$HK     = @(
  '-hostkey','49:73:6a:00:92:6f:f7:f8:93:7a:9d:aa:10:3e:53:2a',
  '-hostkey','ed:dc:9b:75:cf:e9:53:c9:99:ed:ca:1f:49:98:df:15',
  '-hostkey','e6:6b:ff:1d:08:02:34:70:bc:c2:33:e1:64:8d:10:3c'
)
$SSH = { param($cmd) & $Plink -batch @HK -pw $env:NAS_PW "$User@$Host" $cmd }
# 口令：$env:NAS_PW 必须是本会话内变量；缺则立即停，绝不硬编码。
if (-not $env:NAS_PW) { throw 'NAS_PW 未设置' }
```

## 步 1 · 冻结

```powershell
git -C $Repo status -sb           # 期望无未提交改动，且与 origin 关系已知
git -C $Repo rev-parse --short HEAD
```

- 有未提交改动：先 `git add` 具体文件并 `git commit -m '<type(scope): msg>'`。
- **顺序铁律**：先 commit，后 build。`build-dist` 注入的是**构建那一刻**的 HEAD；若 build 后再 commit，健康闸必对不上。

## 步 2 · 自检

```powershell
Push-Location $Repo
go build ./... ; if ($LASTEXITCODE) { throw 'go build 失败' }
go vet  ./...  ; if ($LASTEXITCODE) { throw 'go vet 失败' }
go test ./...  ; if ($LASTEXITCODE) { throw 'go test 失败' }
# 仅当改动含 web/static/app.js 时：
node --check web/static/app.js
Pop-Location
```

- `gofmt -l web/` 若只列 `endorse*.go`，属历史遗留，**不在本次范围**。

## 步 3 · 构建

```powershell
& pwsh -NoProfile -File (Join-Path $Repo 'scripts/build-dist.ps1')
```

- 产出：`dist\linux-amd64\{cloudflare-web,cfnat,cfdata,sing-box}`、`dist\ca-certificates.crt`。
- `sing-box` 按 `sing-box.version` stamp 缓存，通常跳过。

## 步 4 · 验标记（构建物确实带本版 HEAD）

```powershell
$head = (git -C $Repo rev-parse --short HEAD).Trim()
$txt  = [IO.File]::ReadAllText((Join-Path $Repo 'dist\linux-amd64\cloudflare-web'), [Text.Encoding]::Latin1)
if (-not $txt.Contains($head)) { throw "二进制未含 HEAD=$head，勿发布" }
```

## 步 5 · 备份锚点 + 传输

远端备份（生成带时间戳锚点，覆盖前必备份）：

```powershell
& $SSH "cd $Root && STAMP=\$(date +%Y%m%d-%H%M%S) && \
  cp -p dist/linux-amd64/cloudflare-web dist/linux-amd64/cloudflare-web.bak-\$STAMP && \
  cp -p docker-compose.yml docker-compose.yml.bak-\$STAMP && \
  cp -p .env .env.bak-\$STAMP && echo STAMP=\$STAMP"
```

传输（**一键脚本无条件推全 6 件并字节校验**；手工链等价如下）：

```powershell
$art = @(
  @((Join-Path $Repo 'dist\linux-amd64\cloudflare-web'), "$Root/dist/linux-amd64/cloudflare-web"),
  @((Join-Path $Repo 'dist\linux-amd64\cfnat'),           "$Root/dist/linux-amd64/cfnat"),
  @((Join-Path $Repo 'dist\linux-amd64\cfdata'),          "$Root/dist/linux-amd64/cfdata"),
  @((Join-Path $Repo 'dist\ca-certificates.crt'),         "$Root/dist/ca-certificates.crt"),
  @((Join-Path $Repo 'docker-compose.yml'),               "$Root/docker-compose.yml"),
  @((Join-Path $Repo 'Dockerfile'),                       "$Root/Dockerfile")
)
foreach ($a in $art) { & $Pscp -batch @HK -pw $env:NAS_PW $a[0] "${User}@${Host}:$a[1]" }

# 字节校验（前四件为构建产物；cfnat/cfdata 不带 gitCommit，只能靠 hash 收口）
foreach ($a in $art[0..3]) {
  $lh = (Get-FileHash -Algorithm SHA256 -LiteralPath $a[0]).Hash.ToLower()
  $rh = ((& $Plink -batch @HK -pw $env:NAS_PW "$User@$Host" "sha256sum '$($a[1])' | cut -d' ' -f1") -join '').Trim().ToLower()
  if ($rh -ne $lh) { throw "字节校验失败: $($a[1])" }
  "hash OK  $($a[1])"
}
```

- **为何要无条件推 `cfnat` / `cfdata` / `ca-certificates.crt`**：`build-dist.ps1` 只给 `cloudflare-web` 注入 `gitCommit`，另两个不带版本；健康闸只查 `web`。故漏推 `cfnat` 会被绿灯放行成「静默旧版」——hash 校验补的就是这个洞。
- `sha256sum` 经 plink 返回真实远端哈希（已三方交叉验证：remote == 本地计算 == 已知常量）。
- `.env` 仍手工编辑（脚本只备份不改），且用追加防重复：`cd $Root && (grep -q '^KEY=' .env || echo 'KEY=value' >> .env)`。

## 步 6 · 重建容器

```powershell
& $SSH "cd $Root && docker compose build && docker compose up -d && sleep 8 && docker ps --filter name=cloudflare-tools --format '{{.Names}} {{.Status}}'"
```

## 步 7 · 健康闸 + 功能验证

```powershell
& $SSH "wget -qO- http://127.0.0.1:8080/api/health"
# 期望 version.gitCommit == 步 4 的 $head，且容器 healthy
```

功能级验证按改动走，例：

```powershell
# 确认 cfnat 参数（scratch 无 shell，用 docker top）
& $SSH "docker top cloudflare-tools -o pid,args"
# 确认新字段存在
& $SSH "wget -qO- http://127.0.0.1:8080/api/status | jq '.forward'"
& $SSH "wget -qO- http://127.0.0.1:8080/api/cfnat/proxy-candidates | jq '.domainLatency'"
```

## 回滚（任一步失败即执行）

```powershell
# 1. 找到最近锚点
& $SSH "ls -1t $Root/dist/linux-amd64/cloudflare-web.bak-* | head -n1"
# 2. 还原二进制与 compose
& $SSH "cd $Root && cp -p dist/linux-amd64/cloudflare-web.bak-<STAMP> dist/linux-amd64/cloudflare-web && \
  cp -p docker-compose.yml.bak-<STAMP> docker-compose.yml && \
  ( [ -f .env.bak-<STAMP> ] && cp -p .env.bak-<STAMP> .env || true )"
# 3. 重建并验证
& $SSH "cd $Root && docker compose build && docker compose up -d && sleep 8 && wget -qO- http://127.0.0.1:8080/api/health"
```

## 发布后（可选）

```powershell
git -C $Repo push origin main   # 确认线上无误后再推
```

- 锚点清理：确认新版本稳定后，可删更旧的 `*.bak-*`，**保留最近一次**。
