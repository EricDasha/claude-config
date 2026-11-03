# 只读探针命令

> 全部只读，不改任何文件。Windows + Git Bash 环境实测。

## 1. 排除本地权限覆盖

```bash
ls ~/.claude/settings.local.json
# 不存在 → 不是权限规则拦截
```

## 2. 探本地代理（cc-switch 等）

```bash
curl -s -m 6 -o /dev/null -w "relay http=%{http_code} t=%{time_total}s\n" \
  http://127.0.0.1:15721/v1/models
```

| 结果 | 判词 |
|---|---|
| `200` + 毫秒级 | 代理健康，病在上游模型通道 |
| 超时 / 拒绝连接 | 代理层问题，先修代理 |

## 3. 探上游端点

用 Node 内置 fetch（避免 Windows shell 转义把 URL 吃掉）：

```bash
node --no-warnings -e "
const u='https://<上游域名>/v1/models';
const t=Date.now();
fetch(u,{signal:AbortSignal.timeout(10000)})
  .then(r=>console.log('status',r.status,'ms',Date.now()-t))
  .catch(e=>console.log('ERR',e.cause?.code||e.message,Date.now()-t));
"
```

带密钥探测（密钥从环境变量读，不进命令行历史）：

```bash
node --no-warnings -e "
const u='https://<上游域名>/v1/models';
fetch(u,{headers:{Authorization:'Bearer '+process.env.UP_KEY},
         signal:AbortSignal.timeout(10000)})
  .then(r=>r.json().then(j=>({s:r.status,n:(j.data||[]).length})).catch(()=>({s:r.status})))
  .then(o=>console.log(o))
  .catch(e=>console.log('ERR',e.cause?.code||e.message));
"
```

| 返回 | 判词 |
|---|---|
| `401` 且 <3s | 端点活着，需密钥或密钥失效 |
| `503` / `502` | **上游模型过载** —— 本 skill 的主病因 |
| `200` 但 >5s | 上游慢，可能间歇触发超时拒绝 |
| 超时 / DNS 失败 | 网络或域名问题 |

## 4. 查 cc-switch 历史战绩

```bash
node --no-warnings -e "
const {DatabaseSync}=require('node:sqlite');
const db=new DatabaseSync(process.env.HOME+'/.cc-switch/cc-switch.db',{readOnly:true});
const q=db.prepare(\"SELECT request_model,status_code,count(*) c,max(created_at) last \
  FROM proxy_request_logs GROUP BY request_model,status_code \
  ORDER BY last DESC LIMIT 20\").all();
for(const x of q) console.log(JSON.stringify({...x}));
"
```

注意事项：
- `created_at` 是 **epoch 秒**，不是 ISO 字符串，直接跟字符串比较会得到空结果。
- `request_model` 存的是**上游模型名**（如 `deepseek-v4.1-flash`），不是 provider 的别名。
- `provider_id` 为 `_opencode_session` 的记录来自 opencode，**不代表 Claude Code 通道**。

## 5. 查 provider 定义（cc-switch 权威源）

```bash
node --no-warnings -e "
const {DatabaseSync}=require('node:sqlite');
const db=new DatabaseSync(process.env.HOME+'/.cc-switch/cc-switch.db',{readOnly:true});
const p=db.prepare('SELECT id,name,app_type,settings_config FROM providers').all();
for(const x of p){
  const j=JSON.parse(x.settings_config||'{}');
  const base=j.options?.baseURL||j.env?.ANTHROPIC_BASE_URL||'-';
  console.log(x.app_type,'|',x.name,'|',base);
}
"
```

> 输出可能含明文 API Key。**只看 baseURL 与模型列表，不要把整段 `settings_config` 贴进对话。**

## 6. 查代理开关状态

```bash
node --no-warnings -e "
const {DatabaseSync}=require('node:sqlite');
const db=new DatabaseSync(process.env.HOME+'/.cc-switch/cc-switch.db',{readOnly:true});
const r=db.prepare('SELECT app_type,proxy_enabled,enabled,listen_port,auto_failover_enabled FROM proxy_config').all();
for(const x of r) console.log(JSON.stringify({...x}));
"
```

`proxy_enabled=0` 但端口有响应 ⇒ 该端口不是 cc-switch 代理在提供服务，另有进程占用。
