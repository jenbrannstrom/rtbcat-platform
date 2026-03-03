# 第 15 章：故障排除手册

*适用读者：运维、平台工程师*

## 登录循环

**症状：** 用户进入登录页面，完成认证后被重定向回登录页面，无限循环。

**根本原因模式：** 任何数据库故障导致 `_get_or_create_oauth2_user()`
静默失败。`/auth/check` 返回 `{authenticated: false}`。前端重定向到
`/oauth2/sign_in`。循环。

**常见触发因素：**
- Cloud SQL Proxy 容器宕机或重启后未重启 API
- VM 与 Cloud SQL 实例之间的网络分区
- Cloud SQL 实例维护或重启

**检测：**
- 浏览器：重定向计数器在 30 秒内 2 次重定向后触发，显示错误/重试界面而
  非继续循环
- API：数据库不可达时 `/auth/check` 返回 HTTP 503（非 200），响应中
  包含 `auth_error`
- 日志：在 catscan-api 日志中查找连接拒绝或超时错误

**修复：**
1. 检查 Cloud SQL Proxy：`sudo docker ps | grep cloudsql`
2. 如果已停止：`sudo docker compose -f docker-compose.gcp.yml restart cloudsql-proxy`
3. 等待 10 秒，然后重启 API：
   `sudo docker compose -f docker-compose.gcp.yml restart api`
4. 验证：`curl -sS http://localhost:8000/health`

**预防：** 三层修复（2026 年 2 月已应用）：
1. 后端通过 `request.state.auth_error` 传播数据库错误
2. 数据库不可达时 `/auth/check` 返回 503
3. 前端有重定向计数器（30 秒内最多 2 次）+ 错误/重试界面

## 数据新鲜度超时

**症状：** `/uploads/data-freshness` 返回 500、超时，或运行时健康门控
显示 BLOCKED 数据健康状态。

**根本原因模式：** 数据新鲜度查询扫描大表（`rtb_daily` 8400 万行，
`rtb_bidstream` 2100 万行）。如果查询计划退化为顺序扫描而非使用索引，
可能需要 160+ 秒。

**检测：**
1. 从 VM 直接访问端点：
   ```bash
   curl -sS --max-time 60 -H 'X-Email: cat-scan@rtb.cat' \
     'http://localhost:8000/uploads/data-freshness?days=14&buyer_id=<ID>'
   ```
2. 如果超时或返回 500，检查查询计划：
   ```bash
   sudo docker exec catscan-api python -c "
   import os, psycopg
   conn = psycopg.connect(os.environ['POSTGRES_DSN'])
   for r in conn.execute('EXPLAIN (ANALYZE, BUFFERS) <query>').fetchall():
       print(list(r.values())[0])
   "
   ```
3. 在大表上查找 `Parallel Seq Scan`，这就是问题所在。

**修复模式：**
- 将 GROUP BY 查询重写为 `generate_series + EXISTS` 以强制索引查找。
  参见[数据库操作](14-database.md)了解模式详情。
- 确保使用 `SET LOCAL statement_timeout`（而非 `SET` + `RESET`）。
- 检查所有目标表上是否存在 `(buyer_account_id, metric_date DESC)` 索引。

## Gmail 导入失败

**症状：** 数据新鲜度网格显示近期日期的"缺失"单元格。导入历史无最近条目。

**检测：**
```bash
curl -sS -H 'X-Email: cat-scan@rtb.cat' \
  http://localhost:8000/gmail/status
```

检查：`last_reason`、`unread` 计数、`latest_metric_date`。

**常见原因：**
- Gmail OAuth 令牌过期：在 `/settings/accounts` > Gmail 标签页重新授权
- Cloud SQL Proxy 宕机：Gmail 导入写入 Postgres，因此数据库必须可达
- 大量 `unread` 计数（30+）：导入可能卡住或邮箱有积压

**修复：**
1. 如果 `last_reason` 显示错误：从界面或 API 重启导入任务
2. 如果令牌过期：重新授权 Gmail 集成
3. 如果 Cloud SQL 宕机：先修复数据库连接（参见登录循环）

## 容器重启顺序

**症状：** API 日志在启动时显示"connection refused"到端口 5432。

**原因：** API 容器在 Cloud SQL Proxy 就绪之前启动。

**修复：** 按正确顺序重启：
```bash
sudo docker compose -f docker-compose.gcp.yml up -d cloudsql-proxy
sleep 10
sudo docker compose -f docker-compose.gcp.yml up -d api
```

或重启所有容器（compose 处理依赖关系）：
```bash
sudo docker compose -f docker-compose.gcp.yml up -d --force-recreate
```

## SET statement_timeout 语法错误

**症状：** 端点返回 500，错误为：
`syntax error at or near "$1" LINE 1: SET statement_timeout = $1`

**原因：** psycopg3 将 `%s` 转换为 `$1` 用于服务端参数绑定，但
PostgreSQL 的 `SET` 命令不支持参数占位符。

**修复：** 使用 f-string 和经过验证的整数：
```python
# 错误：
conn.execute("SET statement_timeout = %s", (timeout_ms,))

# 正确：
timeout_ms = max(int(statement_timeout_ms), 1)  # 验证的整数
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
```

## 运行时健康门控失败

**症状：** `v1-runtime-health-strict.yml` 工作流失败。

**排查：**
1. 检查工作流日志：`gh run view <id> --log-failed`
2. 区分 FAIL 和 BLOCKED：
   - **FAIL** = 出了问题，需调查
   - **BLOCKED** = 依赖缺失（无数据、无端点），可能是已有问题
3. 常见的已有 BLOCKED 原因：
   - "rtb_quality_freshness state is unavailable"：该买方/时段无质量数据
   - "proposal has no billing_id"：数据设置问题
   - "QPS page API rollup missing required paths"：分析端点尚未填充数据
4. 与之前的运行对比，区分回归和已有问题。

## 相关内容

- [健康监控](13-health-monitoring.md)：监控工具
- [数据库操作](14-database.md)：查询和索引详情
- [部署](12-deployment.md)：部署修复
