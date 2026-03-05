# 第 13 章：健康监控与诊断

*适用读者：运维、平台工程师*

## 健康端点

### `/api/health`：存活检查

返回基本 API 状态、git SHA 和版本。部署工作流和外部监控使用。

```bash
curl -sS https://your-deployment.example.com/api/health | jq .
```

### `/system/data-health`：数据完整性

返回每个买方的数据健康状态，包括每种报告类型的新鲜度状态。接受 `days`、
`buyer_id` 和 `availability_state` 参数。

引导清单和运行时健康检查使用此端点。

## 系统状态页面（`/settings/system`）

界面显示：

| 检查项 | 监控内容 |
|--------|---------|
| Python | 运行时版本和可用性 |
| Node | Next.js 构建和 SSR 状态 |
| FFmpeg | 视频缩略图生成能力 |
| 数据库 | Postgres 连接和行数 |
| 缩略图 | 批量生成状态和队列 |
| 磁盘空间 | VM 磁盘使用情况 |

## 运行时健康脚本

这些脚本是验证系统端到端正常工作的运维基础。

### `diagnose_v1_buyer_report_coverage.sh`

诊断特定买方 CSV 覆盖缺失的原因。

```bash
export CATSCAN_CANARY_EMAIL="user.com"
scripts/diagnose_v1_buyer_report_coverage.sh \
  --buyer-id <BUYER_ID> \
  --timeout 180 \
  --days 14
```

按顺序检查：
1. 席位映射：buyer_id -> bidder_id
2. 导入矩阵：按 CSV 类型的通过/失败/未导入
3. 数据新鲜度：已导入/缺失单元格覆盖
4. 导入历史：最近的导入行
5. Gmail 状态：未读数、最后原因、最新指标日期

结果：PASS 或 FAIL 并附具体诊断。

### `run_v1_runtime_health_strict_dispatch.sh`

运行完整的运行时健康检查，包括：

- API 健康
- 数据健康（新鲜度和维度覆盖）
- 转化健康和就绪状态
- QPS 启动延迟
- QPS 页面 SLO 摘要
- 优化器经济指标和模型
- 模型端点验证
- 评分+建议工作流
- 建议生命周期
- 回滚试运行

每项检查返回 PASS、FAIL 或 BLOCKED（附原因）。

### CI 工作流：`v1-runtime-health-strict.yml`

在 CI 中运行严格检查。通过 workflow_dispatch 手动触发。

```bash
gh workflow run v1-runtime-health-strict.yml \
  --ref unified-platform \
  -f api_base_url="https://your-deployment.example.com/api" \
  -f buyer_id="<BUYER_ID>" \
  -f canary_profile="balanced" \
  -f canary_timeout_seconds="180"
```

## 金丝雀认证

运行时脚本使用环境变量认证：

| 变量 | 用途 |
|------|------|
| `CATSCAN_CANARY_EMAIL` | 直接 API 调用的 X-Email 头（VM 本地） |
| `CATSCAN_BEARER_TOKEN` | Bearer 令牌（CI 环境，存储在 GitHub secrets） |
| `CATSCAN_SESSION_COOKIE` | OAuth2 Proxy 会话 Cookie（CI 环境） |

从 VM 主机，使用 `CATSCAN_CANARY_EMAIL` 配合 `http://localhost:8000`。
从 CI（外部），使用 `CATSCAN_BEARER_TOKEN` 或 `CATSCAN_SESSION_COOKIE`
配合 `https://your-deployment.example.com/api`。

## 结果解读

| 状态 | 含义 |
|------|------|
| **PASS** | 检查通过，系统健康 |
| **FAIL** | 检查失败，立即调查 |
| **BLOCKED** | 由于依赖项无法完成检查（如该买方无数据、缺少端点）。不一定是代码缺陷。 |

## 相关内容

- [部署](12-deployment.md)：部署验证
- [故障排除](15-troubleshooting.md)：当健康检查失败时
- 面向媒体买手：[数据导入](09-data-import.md)用买手友好的方式说明
  数据新鲜度网格。
