---
name: git-master
description: Git expert for atomic commits, rebase/squash, and history archaeology (blame, bisect, log -S pickaxe). Use whenever committing, splitting a messy working tree into logical commits, rewriting local history, resolving rebase conflicts, or hunting down which commit introduced a change. 触发词：提交、拆提交、原子提交、rebase、squash、压缩提交、查历史、定位是哪次提交引入的、git 操作。
license: MIT
---

# git-master

Git 操作专家。核心是**原子提交**和**历史考古**——把一坨改动拆成能被 review、能被 revert 的独立提交，以及在历史里精确定位一次变更。

## 何时使用

- 有未提交的改动要 commit（尤其是改了多个不相关文件）
- 需要把一个巨大的 WIP 提交拆成多个逻辑提交
- rebase / squash / 修改历史
- rebase 冲突解决
- 找「这行代码是哪次提交改的」「哪个提交引入了这个 bug」

## 铁律

1. **绝不添加 AI 署名。** 不要加 `Co-authored-by`、`Generated with`、`Ultraworked with` 之类的 trailer 或 footer。提交信息只写人类会写的内容。
2. **绝不重写已推送的历史**，除非用户明确要求。`git push --force` 前必须确认目标分支只有自己用。
3. **绝不 `git add -A` / `git add .`** 一把梭。显式列出文件，否则会把构建产物、临时文件、密钥一起提交。
4. **先看再动。** 动手前先 `git status --short` + `git diff`，理解改了什么。
5. **提交前跑测试**（如果仓库有测试）。不确定就跑最小的相关测试集。

## 原子提交：拆分规则

多个不相关改动挤在一个提交里，是这个 skill 要解决的头号问题。

| 改动文件数 | 最少提交数 |
| --- | --- |
| 1–2 | 1 |
| 3–4 | 2 |
| 5–9 | 3 |
| 10+ | 5 |

**怎么分组**——按「一个提交能不能被独立理解、独立 revert」来分：

- 按关注点分：重构 / 功能 / 修 bug / 文档 / 测试 / 构建配置，各自独立
- 按模块分：不同目录、不同子系统分开
- 格式化改动**必须**单独一个提交（否则真实改动会被空白噪声淹没）
- 依赖升级单独一个提交
- 测试改动跟着它测的代码走，除非测试是独立的补充

**拆分手法**：

```bash
# 交互式暂存（推荐，逐个 hunk 选）
git add -p <file>

# 直接选整文件
git add <file1> <file2>

# 把当前暂存区先固化，再继续拆剩下的
git stash --keep-index        # 暂存已 add 的，其余退回工作区
```

## 提交信息格式

采用 Conventional Commits，标题行 ≤ 72 字符：

```
<type>(<scope>): <祈使句描述>

<可选正文：为什么这么改，而不是改了什么>
```

`type`：`feat` `fix` `refactor` `perf` `docs` `test` `build` `ci` `chore` `revert`

- 标题用祈使句：「fix login redirect」而不是「fixed」/「fixes」
- 正文写**动机**和**权衡**，改动内容 `git diff` 已经说了
- 破坏性变更：`feat(api)!: ...` 并在正文加 `BREAKING CHANGE:` 段

## 历史考古

**找「这行是谁改的」**：

```bash
git blame -L 40,60 -- path/to/file.py
git blame -w -C -C -- path/to/file.py   # 忽略空白、跨文件追踪移动的代码
```

**找「哪个提交引入了某个字符串」**（pickaxe，最常用）：

```bash
git log -S "exact_string" --oneline -- path/     # 增删该字符串的提交
git log -G "regex" --oneline                     # 匹配 diff 内容的正则
git log -p -S "exact_string" -- path/            # 带完整 diff
```

**找「什么时候开始坏的」**（二分）：

```bash
git bisect start
git bisect bad                  # 当前是坏的
git bisect good <known-good>    # 已知好的提交
# git 会切到中间点，测试后标记：
git bisect good / git bisect bad
git bisect reset                # 结束后回到原分支
```

自动化二分（有可脚本化的判定命令时首选）：

```bash
git bisect start HEAD <known-good>
git bisect run ./test.sh         # 退出码 0 = good，非 0 = bad
git bisect reset
```

**其他**：

```bash
git log --oneline --graph --decorate -20
git log --follow -- path/renamed_file.py    # 跟踪重命名后的文件历史
git log --diff-filter=D --summary           # 找被删除的文件
git reflog                                  # 找回「丢掉」的提交（救命用）
git show <sha> --stat
```

## rebase / squash

**把分支变基到最新主干**：

```bash
git fetch origin
git rebase origin/main
# 冲突时：编辑文件 → git add <file> → git rebase --continue
# 想放弃：git rebase --abort
```

**压缩最近 N 个提交**：

```bash
git rebase -i HEAD~5      # 把除第一个外的 pick 改成 squash/fixup
git reset --soft HEAD~3 && git commit    # 更简单的合并手法
```

**rebase 冲突排查技巧**：

```bash
git diff                    # 看当前冲突标记
git checkout --ours <file>  # 取当前分支版本
git checkout --theirs <file># 取被合入版本
git rerere                  # 记住冲突解法，重复冲突自动应用
```

**注意**：`git rebase -i` 会打开编辑器，在非交互环境里跑不了。要么用 `GIT_SEQUENCE_EDITOR` 注入脚本，要么改用 `git reset --soft` 的等价手法。

## 安全检查清单

提交或改历史前过一遍：

```bash
git status --short              # 确认没有意外文件
git diff --cached               # 确认暂存内容正确
git diff --cached --check       # 检查空白错误和冲突标记
git log --oneline -5            # 确认历史状态
```

- 检查是否误提交了 `.env`、密钥、大文件、`node_modules/`、构建产物
- 误提交敏感信息 → 立刻处理（改密钥优先于改历史）
- 分支已推送且他人可能已拉取 → 不要 rebase/force push
