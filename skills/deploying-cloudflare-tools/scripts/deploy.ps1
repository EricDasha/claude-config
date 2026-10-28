#!/usr/bin/env pwsh
#Requires -Version 7
<#
.SYNOPSIS
  cloudflare-tools 一键发布到生产 NAS。
.DESCRIPTION
  七步闭环：冻结 → 自检 → 构建 → 验标记 → 备份锚点 → 传输 → 重建 → 健康闸。
  配套 skill: deploying-cloudflare-tools。口令只走 $env:NAS_PW，绝不落盘。
.PARAMETER Repo
  仓库根路径（默认 G:\EricDasha.github.io\cloudflare）。
.PARAMETER Msg
  非空则先把工作树全部改动 git add -A 并 commit（commit 必须先于 build）。
.PARAMETER Push
  健康闸通过后 git push origin main。
.PARAMETER Rollback
  只回滚：还原远端最近一次 *.bak-<stamp> 锚点并重建，不碰本地。
.PARAMETER Verify
  只读体检：容器状态、健康、cfnat 参数、转发与域名延迟实况，不改任何东西。
.PARAMETER DryRun
  只跑本地部分（自检 + 构建 + 验标记），不触碰远端。
.PARAMETER SkipTests
  跳过 go test（仅在确知风险时）。
.EXAMPLE
  pwsh deploy.ps1 -Msg "feat(web): xxx"
.EXAMPLE
  pwsh deploy.ps1 -Push
.EXAMPLE
  pwsh deploy.ps1 -Rollback
#>
[CmdletBinding()]
param(
  [string]$Repo = ($env:CF_REPO ?? 'G:\EricDasha.github.io\cloudflare'),
  [string]$Msg,
  [switch]$Push,
  [switch]$Rollback,
  [switch]$Verify,
  [switch]$DryRun,
  [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'

$NasHost = $env:NAS_HOST ?? '192.168.1.50'
$User     = $env:NAS_USER ?? 'administer'
$Root     = $env:NAS_ROOT ?? '/vol1/1000/Docker/CFNat'
$Plink    = $env:PLINK ?? 'C:\Program Files\PuTTY\plink.exe'
$Pscp     = $env:PSCP  ?? 'C:\Program Files\PuTTY\pscp.exe'
$HK = @(
  '-hostkey','49:73:6a:00:92:6f:f7:f8:93:7a:9d:aa:10:3e:53:2a',
  '-hostkey','ed:dc:9b:75:cf:e9:53:c9:99:ed:ca:1f:49:98:df:15',
  '-hostkey','e6:6b:ff:1d:08:02:34:70:bc:c2:33:e1:64:8d:10:3c'
)

function Write-Step([string]$Tag, [string]$Text) {
  Write-Host "`n== [$Tag] $Text ==" -ForegroundColor Cyan
}
function Invoke-Remote([string]$Cmd) {
  & $Plink -batch @HK -pw $env:NAS_PW "$User@$NasHost" $Cmd
  if ($LASTEXITCODE -ne 0) { throw "远端命令失败(exit $LASTEXITCODE): $Cmd" }
}
function Copy-To([string]$Local, [string]$Remote) {
  & $Pscp -batch @HK -pw $env:NAS_PW $Local "${User}@${NasHost}:$Remote"
  if ($LASTEXITCODE -ne 0) { throw "pscp 失败: $Local -> $Remote" }
}
function Get-Remote([string]$Cmd) {
  $out = (& $Plink -batch @HK -pw $env:NAS_PW "$User@$NasHost" $Cmd) -join "`n"
  if ($LASTEXITCODE -ne 0) { throw "远端命令失败(exit $LASTEXITCODE): $Cmd" }
  return $out
}
# cfnat / cfdata 不带 gitCommit（build-dist 只给 web 注入），故用字节级校验收口，
# 否则「只推 web、漏推 cfnat」会静默上线旧版并被健康闸放行。
function Get-LocalHash([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { throw "本地产物缺失: $Path" }
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLower()
}
function Assert-RemoteHash([string]$Local, [string]$Remote) {
  $lh = Get-LocalHash $Local
  $rh = (Get-Remote "sha256sum '$Remote' 2>/dev/null | cut -d' ' -f1").Trim().ToLower()
  if (-not $rh) { throw "远端文件缺失（从未传输或被清）: $Remote" }
  if ($rh -ne $lh) {
    throw "字节校验失败(远端≠本地): $Remote`n  local =`n    $lh`n  remote=`n    $rh"
  }
  Write-Host "  hash OK  $Remote"
}

if (-not (Test-Path -LiteralPath $Repo)) { throw "仓库不存在: $Repo" }
Set-Location -LiteralPath $Repo

# ---------------- 只读体检模式 ----------------
if ($Verify) {
  if (-not $env:NAS_PW) { throw 'NAS_PW 未设置' }
  Write-Step 'V1' '容器状态'
  Invoke-Remote "docker ps --filter name=cloudflare-tools --format '{{.Names}} {{.Status}}'"
  Write-Step 'V2' '健康 / gitCommit'
  Write-Host (Get-Remote "wget -qO- http://127.0.0.1:8080/api/health")
  Write-Step 'V3' 'cfnat 运行参数（sticky / task / tls）'
  Invoke-Remote "docker top cloudflare-tools -o pid,args | grep -oE '\-(sticky|random|task|tls)=[a-z0-9]+' | sort -u"
  Write-Step 'V4' '在途转发实况'
  Invoke-Remote "wget -qO- http://127.0.0.1:8080/api/status | jq -c '.forward'"
  Write-Step 'V5' '域名延迟'
  Invoke-Remote "wget -qO- http://127.0.0.1:8080/api/cfnat/proxy-candidates | jq -c '.domainLatency'"
  Write-Host "`n✓ 体检完成（只读）" -ForegroundColor Green
  return
}

# ---------------- 回滚模式 ----------------
if ($Rollback) {
  if (-not $env:NAS_PW) { throw 'NAS_PW 未设置' }
  Write-Step 'R1' '定位最近回滚锚点'
  $anchor = (Get-Remote "ls -1t $Root/dist/linux-amd64/cloudflare-web.bak-* 2>/dev/null | head -n1").Trim()
  if (-not $anchor) { throw '未找到任何 *.bak-* 锚点，无法回滚' }
  $stamp = ($anchor -replace '.*cloudflare-web\.bak-', '')
  Write-Host "锚点: $anchor (stamp=$stamp)"
  Write-Step 'R2' '还原二进制 + compose + .env'
  Invoke-Remote "cd $Root && cp -p dist/linux-amd64/cloudflare-web.bak-$stamp dist/linux-amd64/cloudflare-web && cp -p docker-compose.yml.bak-$stamp docker-compose.yml && ( [ -f .env.bak-$stamp ] && cp -p .env.bak-$stamp .env || true )"
  Write-Step 'R3' '重建并验健康'
  Invoke-Remote "cd $Root && docker compose build && docker compose up -d && sleep 8 && wget -qO- http://127.0.0.1:8080/api/health"
  Write-Host "`n✓ 回滚完成 -> $stamp" -ForegroundColor Green
  return
}

# ---------------- 冻结 ----------------
Write-Step '1' '冻结工作树'
$dirty = (& git status --porcelain)
if ($dirty) {
  if (-not $Msg) {
    throw "工作树有未提交改动；加 -Msg 提交，或先手动 commit。`n$dirty"
  }
  & git add -A
  if ($LASTEXITCODE -ne 0) { throw 'git add 失败' }
  & git commit -m $Msg
  if ($LASTEXITCODE -ne 0) { throw 'git commit 失败' }
}
$head = (& git rev-parse --short HEAD).Trim()
Write-Host "HEAD = $head"

# ---------------- 自检 ----------------
Write-Step '2' '自检 build / vet / test'
& go build ./... ; if ($LASTEXITCODE -ne 0) { throw 'go build 失败' }
& go vet  ./... ; if ($LASTEXITCODE -ne 0) { throw 'go vet 失败' }
if (-not $SkipTests) { & go test ./... ; if ($LASTEXITCODE -ne 0) { throw 'go test 失败' } }
if (Test-Path 'web/static/app.js') {
  & node --check 'web/static/app.js'
  if ($LASTEXITCODE -ne 0) { throw 'node --check 失败' }
}

# ---------------- 构建 ----------------
Write-Step '3' '构建 linux/amd64'
& (Join-Path $Repo 'scripts/build-dist.ps1')
if ($LASTEXITCODE -ne 0) { throw 'build-dist 失败' }

# ---------------- 验标记 ----------------
Write-Step '4' "验二进制标记 ($head)"
$webBin = Join-Path $Repo 'dist/linux-amd64/cloudflare-web'
$txt = [IO.File]::ReadAllText($webBin, [Text.Encoding]::Latin1)
if (-not $txt.Contains($head)) { throw "二进制未含 HEAD=$head，勿发布" }
Write-Host '标记 OK'

if ($DryRun) {
  Write-Host "`n✓ DryRun 完成（未触碰远端）" -ForegroundColor Green
  return
}
if (-not $env:NAS_PW) { throw 'NAS_PW 未设置' }

# ---------------- 备份 ----------------
Write-Step '5' '远端备份锚点'
$stamp = (Get-Date -Format 'yyyyMMdd-HHmmss')
Invoke-Remote "cd $Root && cp -p dist/linux-amd64/cloudflare-web dist/linux-amd64/cloudflare-web.bak-$stamp && cp -p docker-compose.yml docker-compose.yml.bak-$stamp && cp -p .env .env.bak-$stamp && echo anchored-$stamp"

# ---------------- 传输 + 字节校验 ----------------
# cfnat/cfdata/ca-certificates.crt 必须与 web 同批传输并校验：
# 它们不带 gitCommit，漏推会被健康闸放行成「静默旧版」。
Write-Step '6' '传输产物 + 字节校验'
$artifacts = @(
  @( (Join-Path $Repo 'dist/linux-amd64/cloudflare-web'), "$Root/dist/linux-amd64/cloudflare-web" ),
  @( (Join-Path $Repo 'dist/linux-amd64/cfnat'),           "$Root/dist/linux-amd64/cfnat" ),
  @( (Join-Path $Repo 'dist/linux-amd64/cfdata'),          "$Root/dist/linux-amd64/cfdata" ),
  @( (Join-Path $Repo 'dist/ca-certificates.crt'),         "$Root/dist/ca-certificates.crt" ),
  @( (Join-Path $Repo 'docker-compose.yml'),               "$Root/docker-compose.yml" ),
  @( (Join-Path $Repo 'Dockerfile'),                       "$Root/Dockerfile" )
)
foreach ($a in $artifacts) { Copy-To $a[0] $a[1] }
foreach ($a in $artifacts[0..3]) { Assert-RemoteHash $a[0] $a[1] }

# ---------------- 重建 ----------------
Write-Step '7' '重建容器'
Invoke-Remote "cd $Root && docker compose build && docker compose up -d && sleep 8 && docker ps --filter name=cloudflare-tools --format '{{.Names}} {{.Status}}'"

# ---------------- 健康闸 ----------------
Write-Step '8' '健康闸'
$health = Get-Remote "wget -qO- http://127.0.0.1:8080/api/health"
Write-Host $health
if ($health -notmatch [regex]::Escape($head)) { throw "健康闸失败：线上 gitCommit != $head" }
Write-Host "`n✓ 发布完成，线上 gitCommit = $head" -ForegroundColor Green

# ---------------- 推送 ----------------
if ($Push) {
  Write-Step '9' '推 origin/main'
  & git push origin main
  if ($LASTEXITCODE -ne 0) { throw 'git push 失败' }
  Write-Host '✓ 已推送' -ForegroundColor Green
}
