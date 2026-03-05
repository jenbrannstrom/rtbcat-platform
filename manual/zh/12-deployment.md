# 第 12 章：部署

*适用读者：运维、平台工程师*

## CI/CD 流水线

```
推送到 unified-platform
         │
         ▼
build-and-push.yml（自动）
  ├── 运行合约和恢复测试
  ├── 构建 API 镜像
  ├── 构建 Dashboard 镜像
  └── 推送到 Artifact Registry
         │
         ▼ （手动触发）
deploy.yml（workflow_dispatch）
  ├── 通过 IAP 隧道 SSH 到 VM
  ├── VM 上 git pull
  ├── docker compose pull（预构建镜像）
  ├── docker compose up -d --force-recreate
  ├── 健康检查（等待 60 秒 + curl localhost:8000/health）
  └── 部署后合约检查
```

### 为什么部署是手动的

推送时自动部署在 2026 年 1 月的一次事故后被禁用，当时自动部署与手动 SSH
部署冲突，导致容器损坏和数据丢失。部署工作流现在需要：

1. 通过 GitHub Actions UI 手动触发（"Run workflow"）
2. 明确选择目标（staging 或 production）
3. 输入 `DEPLOY` 确认
4. 可选的原因字段用于审计追踪

### 镜像标签

镜像使用短 git SHA 标记：`sha-XXXXXXX`。部署步骤使用 `GITHUB_SHA` 构造
标签，所以部署的版本总是映射到特定提交。

## 如何部署

1. 验证构建通过：`gh run list --workflow=build-and-push.yml --limit=1`
2. 触发部署：
   ```bash
   gh workflow run deploy.yml \
     --ref unified-platform \
     -f target=production \
     -f confirm=DEPLOY \
     -f reason="你的原因"
   ```
3. 监控：`gh run watch <run_id> --exit-status`
4. 验证：`curl -sS https://your-deployment.example.com/api/health | jq -r '.git_sha,.version'`

## 验证部署

`/api/health` 端点返回：

```json
{
  "git_sha": "94e9cbb0",
  "version": "sha-94e9cbb"
}
```

将 `git_sha` 与你打算部署的提交进行比较。

## 部署后合约检查

部署后，工作流在 API 容器内运行 `scripts/contracts_check.py`。这验证数据
合约（从导入到 API 输出的不可协商规则）是否保持。如果检查失败：

- `ALLOW_CONTRACT_FAILURE=false`（默认）：部署标记为失败。
- `ALLOW_CONTRACT_FAILURE=true`（临时绕过）：部署成功但显示警告。
  此绕过必须在调查后移除。

## Staging vs. 生产

| 环境 | VM 名称 | 域名 |
|------|---------|------|
| Staging | `catscan-vm` | （内部） |
| 生产 | `catscan-vm` | `your-deployment.example.com` |

先部署到 staging，验证后再部署到生产。

## 回滚

回滚方式是部署之前已知正常的提交：

1. 从 git 日志或之前的部署运行中找到最后正常的 SHA。
2. 在 unified-platform 上检出该 SHA（或使用 `--ref` 指定提交）。
3. 触发部署工作流。

没有专门的回滚机制，就是部署旧版本。

## 相关内容

- [架构概述](11-architecture.md)：部署的内容
- [健康监控](13-health-monitoring.md)：验证部署是否成功
