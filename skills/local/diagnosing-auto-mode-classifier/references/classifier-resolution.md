# 审核器模型解析链（claude.exe 2.1.310 实测）

> 提取方式：对 `claude.exe` 做 latin1 字符串扫描，定位导出的函数与关键字常量。
> 二进制路径（npm 分发）：
> `%APPDATA%\npm\node_modules\@anthropic-ai\claude-code\node_modules\@anthropic-ai\claude-code-win32-x64\claude.exe`

## 选择函数 P9e

```js
function P9e(){
  let e = st(), n = Ty();
  // 1. 服务器下发：modelByMainModel[主模型] ?? model
  let r = xbn(n?.modelByMainModel, {vet:(s)=>IRe(s,"modelByMainModel")})
          ?? IRe(n?.model, "model");
  if (r) {
    if (i.CLAUDE_CODE_AUTO_MODE_MODEL)
      warn("Auto mode classifier: ignoring CLAUDE_CODE_AUTO_MODE_MODEL=… "
         + "because a server-configured classifier model (" + r + ") takes priority");
    return {value:r, src:"gb"};                 // 第 1 级
  }
  // 2. 环境变量
  let s = IRe(i.CLAUDE_CODE_AUTO_MODE_MODEL, "env");
  if (s) return {value:s, src:"env"};           // 第 2 级
  // 3. 默认 sonnet5 系
  if ($b().externalSonnet5Probe !== "demoted") {
    let s = u4o(e);
    if (s) return {value:s, src:"default", externalDefault:true};
  }
  // 4. 兜底：主模型名映射
  return {value: tnt(e), src:"default"};
}
```

## 相关常量

```js
Bwn = ["opus55","opus5","opus48","opus47","opus46","opus45"]   // 模型阶梯
pk  = "opus5"
```

`f4o(e)` → `tnr(e)` → 若 `H_e(e) || ZB(e)` 则 `tH(e)`，否则原样返回 `e`。
即第 4 级是**主模型名经 remap 得到**，不是写死的 haiku 或 sonnet。

## 同族环境变量

| 变量 | 用途 |
|---|---|
| `CLAUDE_CODE_AUTO_MODE_MODEL` | 显式固定审核器模型（第 2 级） |
| `CLAUDE_CODE_AUTO_MODE_SERVER` | 指向**外部审核服务**，开启后不走模型判定 |
| `CLAUDE_CODE_AUTO_MODE_TIER` | 审核强度档位 |
| `CLAUDE_CODE_AUTO_MODE_EXTERNAL_PERMISSIONS` | 外部权限模式 |
| `CLAUDE_CODE_AUTO_MODE_TEMPERATURE` | 判定温度，默认 1 |
| `CLAUDE_CODE_AUTO_MODE_OUTCOME_CODES` | 返回结构化判定码 |
| `CLAUDE_CODE_BG_CLASSIFIER_MODEL` | 后台任务的分类器模型（与前台分开） |

## 错误文案对照

| 文案片段 | 含义 |
|---|---|
| `, so auto mode cannot determine the safety of ` | 审核器**不可用**——`<模型>` 前置拼在句首 |
| `Permission for this action was denied by the Claude Code auto mode classifier. Reason: ` | 审核器**正常工作**并判定不安全 |
| `the API's safeguards refuse the classifier's escalated check on it` | 升级判定被上游安全策略拒绝 |
| `The API told auto mode's safety classifier (…) to wait … until then` | 上游限流，附带 `retry_after` |
| `server_unavailable_<原因>` / `server_call_unavailable_<原因>` | 外部审核服务（`AUTO_MODE_SERVER`）侧失败 |
| `server_no_result` / `server_context_stale` / `server_unrecognized_result` | 外部审核服务返回缺失或过期 |

## 调试开关

`settings.json` → `env` → `CLAUDE_CODE_AUTO_MODE_SERVER: "0"` 表示**本地审核服务关闭**，
此时判定只能走模型链（上面四级之一）。
