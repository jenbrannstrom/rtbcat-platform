# 第 17 章：集成

*适用读者：运维、平台工程师*

## GCP 服务账户

Cat-Scan 需要 GCP 服务账户凭据来与 Google API 交互。

**设置：**
1. 在你的 GCP 项目中创建具有 Authorized Buyers API 访问权限的服务账户。
2. 下载 JSON 密钥文件。
3. 在 `/settings/accounts` > API 连接标签页上传。
4. 验证连接：Cat-Scan 测试可达性和权限。

**启用功能：**
- 席位发现（`discoverSeats`）
- 预定向配置同步（`syncPretargetingConfigs`）
- RTB 端点同步（`syncRTBEndpoints`）
- 素材收集（`collectCreatives`）

**项目状态：**
在 `/settings/accounts` 或通过 `GET /integrations/gcp/project-status`
查看 GCP 项目健康状态。这验证服务账户有效、项目可访问且必需的 API 已启用。

## Google Authorized Buyers API

Cat-Scan 从 Authorized Buyers API 同步数据：

| 操作 | 拉取内容 | 何时运行 |
|------|---------|---------|
| **席位发现** | 与服务账户关联的买方账户 | 初始设置、新增席位时 |
| **预定向同步** | Google 上当前的预定向配置状态 | 在 AB 界面进行外部变更后 |
| **RTB 端点同步** | 竞价器端点 URL 和状态 | 初始设置、端点变更后 |
| **素材同步** | 素材元数据（格式、尺寸、目标 URL） | 定期，通过侧边栏"同步全部" |

## Gmail 集成

Google Authorized Buyers 每天通过邮件发送 CSV 报告。Cat-Scan 可自动
导入这些报告。

**设置：**
1. 前往 `/settings/accounts` > Gmail 报告标签页。
2. 授权 Cat-Scan 访问接收 AB 报告的 Gmail 账户。
3. Cat-Scan 将轮询新的报告邮件并导入附件 CSV。

**监控：**
- `GET /gmail/status`：当前状态、未读数、最后原因
- `POST /gmail/import/start`：手动触发导入周期
- `POST /gmail/import/stop`：停止正在运行的导入
- `GET /gmail/import/history`：历史导入记录

**故障排除：**
- 大量未读（30+）：导入积压，可能需要手动干预
- `last_reason: error`：检查日志，可能需要重新授权
- 详细步骤参见[故障排除](15-troubleshooting.md)。

## 语言 AI 提供商

Cat-Scan 使用 AI 检测素材语言并标记地理-语言不匹配（如阿拉伯市场中的
西班牙语广告）。

**支持的提供商：**

| 提供商 | 配置方式 |
|--------|---------|
| Gemini | 在 `/settings/accounts` 配置 API 密钥 |
| Claude | 在 `/settings/accounts` 配置 API 密钥 |
| Grok | 在 `/settings/accounts` 配置 API 密钥 |

通过 `GET/PUT /integrations/language-ai/config` 配置。只需激活一个
提供商。

## 转化 Webhook

外部系统通过 Webhook 向 Cat-Scan 发送转化事件。

**安全层：**

| 层 | 用途 | 配置 |
|----|------|------|
| **HMAC 验证** | 确保请求真实性（使用共享密钥签名） | 在 Webhook 设置中配置共享密钥 |
| **速率限制** | 防止滥用 | 自动，可配置阈值 |
| **新鲜度监控** | 事件停止到达时告警 | 可配置的过期时间窗口 |

**监控：**
- `GET /conversions/security/status`：HMAC 状态、速率限制
  状态、新鲜度状态
- `GET /conversions/health`：整体摄入和聚合健康
- `GET /conversions/readiness`：转化数据是否足够新鲜可信

## 相关内容

- [架构概述](11-architecture.md)：集成在架构中的位置
- [用户管理](16-user-admin.md)：管理服务账户
- 面向媒体买手：[转化与归因](08-conversions.md)介绍买方侧的转化设置。
