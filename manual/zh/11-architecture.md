# 第 11 章：架构概述

*适用读者：运维、平台工程师*

## 系统拓扑

```
                                    互联网
                                       │
                                 ┌─────┴─────┐
                                 │   nginx    │  :443（TLS 终止）
                                 └──┬──────┬──┘
                                    │      │
                          ┌─────────┘      └─────────┐
                          │                          │
                  ┌───────┴────────┐       ┌─────────┴─────────┐
                  │  OAuth2 Proxy  │       │  Next.js 仪表盘    │  :3000
                  │ （Google SSO）  │       │ （静态 + SSR）      │
                  └───────┬────────┘       └───────────────────┘
                          │
                  ┌───────┴────────┐
                  │   FastAPI API  │  :8000
                  │ （118+ 路由）    │
                  └───────┬────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
    ┌─────────┴──────────┐   ┌────────┴────────┐
    │ Cloud SQL Proxy    │   │   BigQuery       │
    │（Postgres 边车）     │   │（批处理分析）      │
    └─────────┬──────────┘   └─────────────────┘
              │
    ┌─────────┴──────────┐
    │  Cloud SQL         │
    │ （Postgres 15）     │
    └────────────────────┘
```

## 容器布局

生产环境运行在单个 GCP 虚拟机上（`catscan-vm`，区域
`asia-southeast1-b`），使用 `docker-compose.gcp.yml`。

| 容器 | 镜像 | 端口 | 角色 |
|------|------|------|------|
| `catscan-api` | `asia-southeast1-docker.pkg.dev/.../api:sha-XXXXXXX` | 8000 | FastAPI 后端 |
| `catscan-dashboard` | `asia-southeast1-docker.pkg.dev/.../dashboard:sha-XXXXXXX` | 3000 | Next.js 前端 |
| `oauth2-proxy` | 标准 oauth2-proxy 镜像 | 4180 | Google OAuth2 认证 |
| `cloudsql-proxy` | Google Cloud SQL Auth Proxy | 5432 | Postgres 连接代理 |
| `nginx` | 标准 nginx + 配置 | 80/443 | 反向代理、TLS、路由 |

## 认证信任链

```
浏览器 → nginx → OAuth2 Proxy → 设置 X-Email 头 → nginx → API
```

1. 浏览器访问 nginx。
2. nginx 将 `/oauth2/*` 路由到 OAuth2 Proxy。
3. OAuth2 Proxy 通过 Google 认证，设置 `X-Email` 头。
4. 后续请求携带 `X-Email` 通过 nginx。
5. API 读取 `X-Email` 并信任它（当 `OAUTH2_PROXY_ENABLED=true` 时）。

**重要：** API 只信任内部流量的 `X-Email`。外部请求中伪造的 `X-Email` 头
会被 nginx 拒绝。

## 为什么使用两个数据库

Cat-Scan 同时使用 Postgres 和 BigQuery，各有不同角色：

| 关注点 | Postgres（Cloud SQL） | BigQuery |
|--------|---------------------|----------|
| **角色** | 运营数据库，服务应用 | 数据仓库，存储原始数据、运行批处理分析 |
| **成本模型** | 固定托管成本，查询无限制 | 按查询付费，基于扫描数据量 |
| **延迟** | 毫秒级响应 | 即使简单查询也有 1-3 秒开销 |
| **并发** | 处理数百个 API 连接 | 不适合并发仪表盘刷新 |
| **数据** | 预聚合汇总、配置、用户数据 | 原始粒度行（每天数百万行） |

模式：BigQuery 是档案仓库；Postgres 是商店货架。你不会让顾客在仓库里
翻找，你把他们需要的东西摆上货架。

## 关键代码结构

```
/api/routers/       FastAPI 路由处理器（118+ 端点）
/services/          业务逻辑层
/storage/           数据库访问（Postgres 仓库、BigQuery 客户端）
/dashboard/src/     Next.js 14 前端（App Router）
/scripts/           运维和诊断脚本
/docs/              架构文档和 AI 代理日志
```

后端遵循 **Router -> Service -> Repository** 模式。Router 处理 HTTP；
Service 包含业务逻辑；Repository 执行 SQL。

## 相关内容

- [部署](12-deployment.md)：系统如何部署
- [数据库操作](14-database.md)：Postgres 细节
- [集成](17-integrations.md)：外部服务连接
