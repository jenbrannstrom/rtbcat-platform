# 术语表

每个术语，两个视角。左列是媒体买手的理解方式，右列是运维工程师在系统中
的对应概念。

| 术语 | 媒体买手定义 | 运维/系统定义 |
|------|------------|-------------|
| **席位** | Google Authorized Buyers 上的买方账户。你按席位来划分分析和定向。 | Postgres 中的 `buyer_account_id`。存储在 `seats` 表。通过 `GET /seats` 同步。 |
| **QPS** | 每秒查询数，即你要求 Google 发送的最大竞价请求速率。Google 会根据账户等级节流实际量。 | 每个预定向配置的上限设置。实际入站速率通过 `rtb_daily` 中的 RTB 漏斗指标监控。 |
| **浪费** | 被你的竞价器拒绝的出价请求所消耗的 QPS，包括错误的地区、错误的尺寸、没有匹配的素材。花了钱却什么都没得到。 | `(total_qps - bids_placed) / total_qps`。从 `rtb_daily` 聚合计算。在漏斗 API 中可见。 |
| **预定向配置** | 控制哪些出价请求到达你的竞价器的规则。每个席位最多 10 个。控制地区、尺寸、格式、平台、发布商。 | 从 Google AB API 同步的可变实体。存储在 `pretargeting_configs`。通过 `/settings/pretargeting` 管理。快照支持回滚。 |
| **漏斗** | 从出价请求到花费的递进：QPS -> 出价 -> 胜出 -> 展示 -> 点击 -> 花费。每一步都有衰减。 | 从 `rtb_daily` 指标计算。由 `GET /analytics/rtb-funnel` 提供。前端缓存 30 分钟。 |
| **素材** | 广告资产：图片、视频、HTML 或原生。有格式、尺寸、目标 URL 和效果历史。 | `creatives` 表中的行。缩略图在 blob 存储中。从 Google AB API 同步。效果数据来自 `rtb_daily` 联合查询。 |
| **活动** | 素材的逻辑分组。用于组织分析和报告。 | `ai_campaigns` 表中的行。与素材多对多关系。支持 AI 自动聚类。 |
| **配置卡** | 显示预定向配置状态、最大 QPS、地区、尺寸、格式和平台的界面面板。 | `PretargetingConfigCard` React 组件。数据来自 `GET /settings/pretargeting-configs`。 |
| **数据新鲜度** | 显示哪些日期已导入数据（"已导入"）vs. 缺口（"缺失"）的网格，按报告类型分列。 | `GET /uploads/data-freshness`。使用 `generate_series + EXISTS` 查询 `rtb_daily`、`rtb_bidstream`、`rtb_quality`、`rtb_bid_filtering`。30 秒语句超时。 |
| **导入** | 将 CSV 效果数据导入 Cat-Scan，通过手动上传或 Gmail 自动导入。 | CSV 解析、验证、去重（通过 `row_hash` 唯一约束），插入目标表。大于 5MB 的文件分块上传。 |
| **回滚** | 将预定向配置变更恢复到之前状态。先预览试运行，然后确认。 | 快照恢复：读取 `pretargeting_snapshots`，将差异应用到 Google AB API，记录新快照。`POST /snapshots/rollback`。 |
| **优化器 / BYOM** | 自动评分分段并提出配置变更建议的系统。使用你自己的外部模型。 | 评分端点通过 HTTP POST 调用。提案存储在 `optimizer_proposals`。生命周期：评分 -> 提案 -> 批准 -> 应用。 |
| **工作流预设** | 安全、平衡或激进，控制优化器提案的大胆程度。 | 评分和提案 API 的 `canary_profile` 参数。影响置信度阈值和变更幅度限制。 |
| **有效 CPM** | 你实际为每千次展示支付的费用，包含浪费和基础设施成本。 | 在 `OptimizerEconomicsService` 中计算。结合 `rtb_daily` 的花费数据和配置的托管成本。 |
| **转化** | 展示后发生的有价值用户行为（购买、注册）。反馈回来以优化定向。 | 通过像素（`GET /conversions/pixel`）或 Webhook（`POST /conversions/webhook`）摄入的事件。存储在转化表中。Webhook 使用 HMAC 验证。 |
| **胜出率** | 胜出 / 出价。衡量你的出价在拍卖中的竞争力。 | `rtb_daily` 中的 `auction_wins / bids_placed`。 |
| **CTR** | 点击 / 展示。衡量你的素材的吸引力。 | `rtb_daily` 中的 `clicks / impressions`。 |
| **运行时健康门控** | （非买方术语） | `v1-runtime-health-strict.yml` CI 工作流。运行端到端检查：API 健康、数据健康、转化、优化器、QPS SLO。每项检查返回 PASS/FAIL/BLOCKED。 |
| **合约检查** | （非买方术语） | `scripts/contracts_check.py`。验证数据合约（从导入到 API 输出的不可协商规则）。部署后运行。失败时阻止发布。 |
| **Cloud SQL Proxy** | （非买方术语） | 提供到 Cloud SQL Postgres 认证访问的边车容器。必须在 API 容器启动前健康。 |
| **X-Email 头** | （非买方术语） | Google 认证后由 OAuth2 Proxy 设置的 HTTP 头。`OAUTH2_PROXY_ENABLED=true` 时 API 信任此头。nginx 会剥离外部请求中的此头。 |
