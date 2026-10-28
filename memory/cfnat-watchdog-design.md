---
name: cfnat-watchdog-design
description: cfnat 看门狗的设计约束与四个致命假象 —— 探针必须能证明流量真的走了代理
metadata:
  node_type: memory
  type: project
  originSessionId: c27d617f-134a-4144-9e24-aff07f859e20
  modified: 2026-10-24T12:39:10.362Z
---

NAS 上 cfnat 隧道看门狗（`scripts/nas/cfnat-watchdog.py`）的**设计硬约束**，2026-10-24 实战演练
逐条踩过才收敛。做任何类似"代理健康探测"的脚本都适用。

**Why**：这条链路上有四个假象会让"探针说正常"变成谎话，其中任何一个没识破，看门狗就是个摆设。

1. **CN 可达站点不能当探针**。最初用 `gstatic.com/generate_204` 判隧道存活：该域名命中
   sing-box 的 geosite-cn/geoip-cn → direct 规则，请求根本不走代理，节点死了它也回 204
   （实测 0.19s，出口是本机 IP）。**必须用出口 IP 对比证明流量真的走了代理**：
   经代理请求 `cloudflare.com/cdn-cgi/trace` 取 `ip=`，与本机直连取到的 IP 比对，
   不同才算健康（`tunnel_health()`）。
2. **改 vless `server` 断不掉隧道**。WS path 里嵌着 `proxyip=proxyip.cmliussss.net?ed=2560`，
   server 指向黑洞时 sing-box 会静默改道 proxyip 域名，隧道照常（实测还更快）。
   **演练必须连 proxyip 一起剥掉**才造得出真故障：`path="/order/anime/play"` +
   `server=192.168.1.50:1`（关闭端口秒拒）。
3. **断链时本机直连 CF 也不通**，所以"先探节点活没活再决定切不切兜底"这个 gate 恒假、
   且扫 13 个候选每次 20s 超时 → 一轮 3 分钟，直接跨过 cron 周期导致锁打架。
   **正解**：删掉 gate，直接轮换兜底——尝试兜底本身就是节点探活（能通即节点活）。
   每轮只试 1 个候选（重启+探测 ≈40s，cron 60s），`fb_idx` 跨轮持久化。
4. **`openssl s_client | openssl x509` 会卡死**。`subprocess` 的 timeout 只杀 shell，
   管道读端挂在死 socket 上，看门狗被拖住数分钟，池恢复了也看不见 → 永远不切回。
   **改用进程内 `socket` + `ssl` 取 DER，检查 CN 字节**（`NODE_CERT_CN =
   b"trojanjd.dpdns.org"`）：池 0.69s / 兜底 0.22s / 关闭端口 0.00s。

**How to apply**：
- 去抖：`DEAD_CONSEC=2` 连续失败才判死（CF 直连握手 1.4~6.8s，单次失败是常态）。
- TG 告警在隧道断时必发不出（proxy EOF、直连超时）→ **`notify()` 待发队列**：
  发不出的攒进 state（上限 20 条），隧道一恢复在健康分支 `flush_pending()` 每轮补发一条。
- 探针超时 20s、恢复确认 `RECOVERY_CONSEC=2`、告警冷却 1800s。
- 演练脚本 `scripts/nas/cfnat-watchdog-drill.py`：故障注入 + `finally` 恢复配置 + 出口 IP 判定。
  实测 PASS 时间线：故障 20:34:02 → 判死 20:35:01 → 兜底接管 20:35:15 → TG 20:35:17 →
  池恢复确认 20:37:09 → 切回 20:37:16 → TG 20:37:28。

相关：[[fnos-nas-ops]]
