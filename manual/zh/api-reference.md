# API 快速参考

这是 Cat-Scan 118+ API 端点的可导航索引，按领域分组。完整的请求/响应
模式请参见交互式 OpenAPI 文档：`https://scan.rtb.cat/api/docs`。

## 核心/系统

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/health` | 存活检查（git_sha、version） |
| GET | `/stats` | 系统统计 |
| GET | `/sizes` | 可用广告尺寸 |
| GET | `/system/status` | 服务器状态（Python、Node、FFmpeg、数据库、磁盘） |
| GET | `/system/data-health` | 每个买方的数据完整性 |
| GET | `/system/ui-page-load-metrics` | 前端性能指标 |
| GET | `/geo/lookup` | 地理 ID 到名称解析 |
| GET | `/geo/search` | 搜索国家/城市 |

## 认证

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/auth/check` | 检查当前会话是否已认证 |
| POST | `/auth/logout` | 结束会话 |

## 席位

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/seats` | 列出买方席位 |
| GET | `/seats/{buyer_id}` | 获取特定席位 |
| PUT | `/seats/{buyer_id}` | 更新席位显示名称 |
| POST | `/seats/populate` | 从数据自动创建席位 |
| POST | `/seats/discover` | 从 Google API 发现席位 |
| POST | `/seats/{buyer_id}/sync` | 同步特定席位 |
| POST | `/seats/sync-all` | 全量同步（所有席位） |
| POST | `/seats/collect-creatives` | 收集素材数据 |

## 素材

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/creatives` | 列出素材（带过滤器） |
| GET | `/creatives/paginated` | 分页素材列表 |
| GET | `/creatives/{id}` | 素材详情 |
| GET | `/creatives/{id}/live` | 实时素材数据（缓存感知） |
| GET | `/creatives/{id}/destination-diagnostics` | 目标 URL 健康状态 |
| GET | `/creatives/{id}/countries` | 国家维度效果细分 |
| GET | `/creatives/{id}/geo-linguistic` | 地理-语言分析 |
| POST | `/creatives/{id}/detect-language` | 自动检测语言 |
| PUT | `/creatives/{id}/language` | 手动语言覆盖 |
| GET | `/creatives/thumbnail-status` | 批量缩略图状态 |
| POST | `/creatives/thumbnails/batch` | 生成缺失缩略图 |

## 活动

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/campaigns` | 列出活动 |
| GET | `/campaigns/{id}` | 活动详情 |
| GET | `/campaigns/ai` | AI 生成的聚类 |
| GET | `/campaigns/ai/{id}` | AI 活动详情 |
| PUT | `/campaigns/ai/{id}` | 更新活动 |
| DELETE | `/campaigns/ai/{id}` | 删除活动 |
| GET | `/campaigns/ai/{id}/creatives` | 活动的素材 |
| DELETE | `/campaigns/ai/{id}/creatives/{creative_id}` | 从活动移除素材 |
| POST | `/campaigns/auto-cluster` | AI 自动聚类 |
| GET | `/campaigns/ai/{id}/performance` | 活动效果 |
| GET | `/campaigns/ai/{id}/daily-trend` | 活动趋势数据 |

## 分析

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/analytics/waste-report` | 整体浪费指标 |
| GET | `/analytics/size-coverage` | 尺寸定向覆盖 |
| GET | `/analytics/rtb-funnel` | RTB 漏斗细分 |
| GET | `/analytics/rtb-funnel/configs` | 配置级漏斗 |
| GET | `/analytics/endpoint-efficiency` | 按端点的 QPS 效率 |
| GET | `/analytics/spend-stats` | 花费统计 |
| GET | `/analytics/config-performance` | 配置随时间的表现 |
| GET | `/analytics/config-performance/breakdown` | 配置字段细分 |
| GET | `/analytics/qps-recommendations` | AI 推荐 |
| GET | `/analytics/performance/batch` | 批量素材效果 |
| GET | `/analytics/performance/{creative_id}` | 单个素材效果 |
| GET | `/analytics/publishers` | 发布商域名指标 |
| GET | `/analytics/publishers/search` | 搜索发布商 |
| GET | `/analytics/languages` | 语言效果 |
| GET | `/analytics/languages/multi` | 多语言分析 |
| GET | `/analytics/geo-performance` | 地理效果 |
| GET | `/analytics/geo-performance/multi` | 多地理分析 |
| POST | `/analytics/import` | CSV 导入 |
| POST | `/analytics/mock-traffic` | 生成测试数据 |

## 设置/预定向

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/settings/rtb-endpoints` | 竞价器 RTB 端点 |
| POST | `/settings/rtb-endpoints/sync` | 同步端点数据 |
| GET | `/settings/pretargeting-configs` | 列出预定向配置 |
| GET | `/settings/pretargeting-configs/{id}` | 配置详情 |
| GET | `/settings/pretargeting-history` | 配置变更历史 |
| POST | `/settings/pretargeting-configs/sync` | 从 Google 同步配置 |
| POST | `/settings/pretargeting-configs/{id}/apply` | 应用配置变更 |
| POST | `/settings/pretargeting-configs/apply-all` | 应用所有待处理变更 |
| PUT | `/settings/pretargeting-configs/{id}` | 批量更新配置 |

## 上传

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/uploads/tracking` | 每日上传摘要 |
| GET | `/uploads/import-matrix` | 按报告类型的导入状态 |
| GET | `/uploads/data-freshness` | 数据新鲜度网格（日期 x 类型） |
| GET | `/uploads/history` | 导入历史 |

## 优化器

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/optimizer/models` | 列出 BYOM 模型 |
| POST | `/optimizer/models` | 注册模型 |
| PUT | `/optimizer/models/{id}` | 更新模型 |
| POST | `/optimizer/models/{id}/activate` | 激活模型 |
| POST | `/optimizer/models/{id}/deactivate` | 停用模型 |
| POST | `/optimizer/models/{id}/validate` | 测试模型端点 |
| POST | `/optimizer/score-and-propose` | 生成提案 |
| GET | `/optimizer/proposals` | 列出活跃提案 |
| GET | `/optimizer/proposals/history` | 提案历史 |
| POST | `/optimizer/proposals/{id}/approve` | 批准提案 |
| POST | `/optimizer/proposals/{id}/apply` | 应用提案 |
| POST | `/optimizer/proposals/{id}/sync-status` | 检查应用状态 |
| GET | `/optimizer/segment-scores` | 分段级评分 |
| GET | `/optimizer/economics/efficiency` | 效率摘要 |
| GET | `/optimizer/economics/effective-cpm` | CPM 分析 |
| GET | `/optimizer/setup` | 优化器配置 |
| PUT | `/optimizer/setup` | 更新优化器配置 |

## 转化

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/conversions/health` | 摄入和聚合状态 |
| GET | `/conversions/readiness` | 来源就绪检查 |
| GET | `/conversions/ingestion-stats` | 按来源/时段的事件计数 |
| GET | `/conversions/security/status` | Webhook 安全状态 |
| GET | `/conversions/pixel` | 像素追踪端点 |

## 快照

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/snapshots` | 列出配置快照 |
| POST | `/snapshots/rollback` | 恢复快照（支持试运行） |

## 集成

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/integrations/credentials` | 上传 GCP 服务账户 JSON |
| GET | `/integrations/service-accounts` | 列出服务账户 |
| DELETE | `/integrations/service-accounts/{id}` | 删除服务账户 |
| GET | `/integrations/language-ai/config` | AI 提供商状态 |
| PUT | `/integrations/language-ai/config` | 配置 AI 提供商 |
| GET | `/integrations/gmail/status` | Gmail 导入状态 |
| POST | `/integrations/gmail/import/start` | 触发手动导入 |
| POST | `/integrations/gmail/import/stop` | 停止导入任务 |
| GET | `/integrations/gmail/import/history` | 导入历史 |
| GET | `/integrations/gcp/project-status` | GCP 项目健康状态 |
| POST | `/integrations/gcp/validate` | 测试 GCP 连接 |

## 管理

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/admin/users` | 列出用户 |
| POST | `/admin/users` | 创建用户 |
| GET | `/admin/users/{id}` | 用户详情 |
| PUT | `/admin/users/{id}` | 更新用户 |
| POST | `/admin/users/{id}/deactivate` | 停用用户 |
| GET | `/admin/users/{id}/permissions` | 用户全局权限 |
| GET | `/admin/users/{id}/seat-permissions` | 用户席位权限 |
| POST | `/admin/users/{id}/seat-permissions` | 授予席位访问 |
| DELETE | `/admin/users/{id}/seat-permissions/{buyer_id}` | 撤销席位访问 |
| POST | `/admin/users/{id}/permissions` | 授予全局权限 |
| DELETE | `/admin/users/{id}/permissions/{sa_id}` | 撤销全局权限 |
| GET | `/admin/audit-log` | 审计追踪 |
| GET | `/admin/stats` | 管理仪表盘统计 |
| GET | `/admin/settings` | 系统配置 |
| PUT | `/admin/settings/{key}` | 更新系统设置 |
