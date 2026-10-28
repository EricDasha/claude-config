---
name: searching-files-with-everything
description: 用 Everything 的命令行程序 es.exe 在全盘范围按文件名、路径、大小、日期、类型即时检索文件，替代逐目录 Glob/ls 的慢速翻找。当要找一个不知道放在哪个盘的文件或目录、或要按条件列出某类文件完整清单时使用。关键词：找文件、全盘搜索、Everything、es.exe、按扩展名找、找大文件、找今天改过的文件。
user-invocable: true
allowed-tools: Bash
---

# 用 Everything 的全盘索引找文件

## 一句话

Everything 在 NTFS 上建了一份全盘文件名索引，`es.exe` 是它的命令行出口。一次查询返回全盘结果，通常几十毫秒——相当于直接查户籍总册，而不是挨家挨户敲门。

## 程序位置

```
E:\Program Files (x86)\Everything\es.exe
```

路径含空格，每次调用都要加引号：

```bash
ES="E:/Program Files (x86)/Everything/es.exe"
"$ES" -version
```

**前提**：Everything 的**界面主程序**（`Everything.exe`，带窗口那个）必须在本用户会话里运行。`es.exe` 只是客户端，通过本地 IPC 向主程序要结果；主程序没跑，会报 `Error 8: Everything IPC not found`。

**坑（2026-10-28 实测）**：托盘里只看到 `Everything.exe` 未必够——`tasklist` 里出现在 `Services` 会话（Session 0）下的那个实例是服务进程，**不响应 `es.exe` 的 IPC**。必须另有一个 `Console` 会话下的 `Everything.exe`。

修复办法：

```bash
# 查是不是只有服务会话的实例
tasklist | grep -i everything     # Session 列必须有一个是 Console
# 补一个界面实例（路径带空格，用引号；不能用 &，会挂住管道）
start "" "E:\Program Files (x86)\Everything\Everything.exe"
sleep 5
"$ES" -n 3 "es.exe"              # 能返回路径即成功
```

注意：直接在 Bash 里执行 `"E:/.../Everything.exe"` 会**阻塞不返回**（它是 GUI 进程）。要么用 `start ""` 起后台，要么扔后台任务。

设了 `allow_multiple_instances=0` 且 `instance_name=` 时不需要 `-instance`；诊断时试过 `-ipc1/-ipc2/-ipc3/-admin` 都不解决问题，病根是界面进程缺席，不是 IPC 版本。

## 基本调用

```bash
"$ES" [选项] <搜索词...>
```

默认输出完整路径，一行一个。搜索词按 Everything 语法解析（见下节）。

## 高频开关

| 开关 | 作用 |
|---|---|
| `-n <次数>` | 限制返回条数。**几乎总该加**，否则全盘命中可能几万行 |
| `-path <目录>` | 只在该目录树内搜索（对应 GUI 的「搜索范围」） |
| `-name` | 只匹配文件名，忽略目录名 |
| `-r <正则>` | 用正则表达式搜索 |
| `-s` | 按名称排序 |
| `-export-csv <文件>` | 导出 CSV，便于二次过滤 |
| `-get-result-count` | 只返回命中总数，不列明细 |
| `-utf8-bom` | 输出带 BOM 的 UTF-8——Windows 终端中文乱码时加这个 |

完整选项以 `"$ES" -help` 为准，上表只列日常高频。

## 搜索语法速查

Everything 搜索框的语法，`es.exe` 同样适用：

| 写法 | 含义 |
|---|---|
| `foo bar` | 同时包含 foo 和 bar（AND） |
| `"完整短语"` | 精确短语，含空格时必加引号 |
| `ext:log` | 扩展名 |
| `path:C:\Users` | 限定路径片段 |
| `*foo*` | 通配符（`*` 任意长度、`?` 单字符） |
| `regex:"^pre.*\.txt$"` | 行内正则 |
| `size:>1mb` | 大于 1MB |
| `dm:today` | 今天修改过 |
| `file:` / `folder:` | 只文件 / 只目录 |

## 常用查询模板

不确定在哪个盘，找某个文件名：

```bash
"$ES" -n 20 "settings.json" -path "C:\Users\Admin"
```

按扩展名找配置文件：

```bash
"$ES" -n 50 "ext:env" -path "G:\EricDasha.github.io"
```

今天改过的 markdown：

```bash
"$ES" -n 100 "ext:md dm:today" -path "C:\Users\Admin\.claude"
```

超过 100MB 的大文件（清理磁盘时）：

```bash
"$ES" -n 50 "size:>100mb" -path "C:\"
```

正则匹配日志：

```bash
"$ES" -n 30 -r "^proxy_.*\.log$" -path "C:\Users\Admin"
```

只要数量：

```bash
"$ES" -get-result-count "ext:tmp" -path "C:\Users\Admin\AppData\Local\Temp"
```

## 和其他搜索工具的取舍

| 场景 | 用什么 |
|---|---|
| 已知目录、已知文件名模式 | Glob 工具就够，不必开子进程 |
| 不知道在哪个盘，要全盘找 | `es.exe` |
| 搜**文件内容** | ripgrep（`rg`）或 Grep 工具；`es.exe` 只看文件名和属性 |
| 按大小、日期、扩展名组合筛 | `es.exe`，条件表达力比 Glob 强得多 |

关键分工：**按名字找 = Everything；按内容找 = ripgrep**。两者互补。

## 注意事项

- **主程序得在跑**。报连接失败时先确认托盘里有 Everything，或 `tasklist | findstr Everything`。
- **一定要限条数**。搜 `*.js` 不加 `-n` 能返回几十万行，白烧上下文。默认给 `-n 100` 以内。
- **路径必须加引号**。`E:\Program Files (x86)` 里的空格和括号不加引号会被 shell 拆开。
- **中文乱码**：默认按系统代码页输出；Git Bash 里乱码就改用 PowerShell，或加 `-utf8-bom` 重定向到文件再读。
- **索引时效**：NTFS 盘实时监听，新文件立即可见；网络盘、FAT32、exFAT 需手动开索引，结果可能滞后。
- 返回的 Windows 反斜杠路径可以直接交给 Read / rg 用。
