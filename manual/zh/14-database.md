# 第 14 章：数据库操作

*适用读者：运维、平台工程师*

## Postgres 生产环境

Cat-Scan 使用 Cloud SQL（Postgres 15）作为唯一的运营数据库。API 通过
Cloud SQL Auth Proxy 边车容器连接 `localhost:5432`。

### 关键表和规模

| 表 | 大约行数 | 存储内容 |
|----|---------|---------|
| `rtb_daily` | ~8400 万 | 每个买方、素材、地区等的每日 RTB 效果 |
| `rtb_bidstream` | ~2100 万 | 按发布商、地区的竞价流细分 |
| `rtb_quality` | 不定 | 质量指标（可见性、品牌安全） |
| `rtb_bid_filtering` | ~18.8 万 | 出价过滤原因和数量 |
| `pretargeting_configs` | 少量 | 预定向配置快照 |
| `creatives` | 少量 | 素材元数据和缩略图 |
| `import_history` | 少量 | CSV 导入记录 |
| `users`、`permissions`、`audit_log` | 少量 | 认证和管理数据 |

### 关键索引

最影响性能的索引模式是：

```sql
CREATE INDEX idx_<table>_buyer_metric_date_desc
    ON <table> (buyer_account_id, metric_date DESC);
```

此索引存在于 `rtb_daily`、`rtb_bidstream`、`rtb_quality` 和
`rtb_bid_filtering` 上。它支持数据新鲜度查询和按买方的分析查询。

其他重要索引：
- `(metric_date, buyer_account_id)`：用于日期范围 + 买方过滤
- `(metric_date, billing_id)`：用于计费范围查询
- `(row_hash)` UNIQUE：导入时去重

### 去重

每行导入数据都经过哈希（`row_hash` 列）。`row_hash` 上的唯一约束防止
重复插入，使重新导入始终安全。

## 连接模型

API 使用**每请求连接**（无连接池）。每次查询创建一个新的
`psycopg.connect()` 调用，通过 `run_in_executor` 包装实现异步兼容。

```python
async def pg_query(sql, params=()):
    loop = asyncio.get_event_loop()
    def _execute():
        with _get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    return await loop.run_in_executor(None, _execute)
```

如果连接开销成为瓶颈，可考虑添加 `psycopg_pool`。

## 语句超时

对于开销大的查询（如跨大表的数据新鲜度查询），API 使用
`pg_query_with_timeout`：

```python
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
cursor = conn.execute(sql, params)
```

关键细节：
- `SET LOCAL` 将超时限定在当前事务范围内，事务结束时（提交或回滚）自动
  重置。
- 默认数据新鲜度超时：30 秒。
- 可通过 `UPLOADS_DATA_FRESHNESS_QUERY_TIMEOUT_MS` 环境变量配置（最小
  1000ms）。
- `SET LOCAL` 避免了使用 `SET` + `RESET` 在 `try/finally` 块中导致的
  事务中止问题（如果查询被超时取消，事务进入中止状态，`RESET` 会失败）。

## 数据新鲜度查询模式

数据新鲜度端点需要知道每种报告类型在哪些日期有数据。高性能的模式使用
`generate_series` + `EXISTS`：

```sql
SELECT d::date AS metric_date, 'bidsinauction' AS csv_type, 1 AS row_count
FROM generate_series(%s::date, CURRENT_DATE - 1, '1 day'::interval) AS d
WHERE EXISTS (
    SELECT 1 FROM rtb_daily
    WHERE metric_date = d::date AND buyer_account_id = %s
    LIMIT 1
)
```

这执行 N 次索引查找（窗口内每天一次），而不是扫描数百万行。对于 14 天
窗口：14 次查找，每次约 0.1ms，vs. 需要 160+ 秒的全表并行顺序扫描。

**为什么 GROUP BY 在这里不适用：** 即使使用 `1 AS row_count`（没有
COUNT），当 GROUP BY 结果集相对于表较大时，查询规划器会选择顺序扫描。
`(buyer_account_id, metric_date DESC)` 索引虽然存在，但规划器估计扫描
8400 万行比执行 440 万次索引读取更便宜。

## BigQuery 的角色

BigQuery 存储原始、细粒度数据并运行批处理分析任务。它不用于实时 API 查询。
模式：

1. 原始 CSV 数据加载到 BigQuery 表。
2. 批处理任务聚合数据。
3. 预聚合结果写入 Postgres。
4. API 从 Postgres 提供服务。

## 数据保留

在 `/settings/retention` 配置。控制历史数据在 Postgres 中保留多长时间。

## 相关内容

- [架构概述](11-architecture.md)：数据库在架构中的位置
- [故障排除](15-troubleshooting.md)：数据库故障模式
- 面向媒体买手：[数据导入](09-data-import.md)介绍用户侧的数据新鲜度网格。
