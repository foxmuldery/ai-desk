# API 草案

> 本文是待实现的接口契约，不代表服务已经可用。实现前需按选定框架与认证方式校验。

## 基础约定

- Base path：/api/v1
- 传输：HTTPS 优先；仅开发阶段可在受控 localhost/LAN 使用 HTTP。
- 认证：每台手机/Agent 使用独立凭据；不得把 Agent 密钥打包进公开前端。
- 时间：ISO 8601 UTC。
- 写操作必须返回明确状态；客户端不得把请求发出等同于任务已接收。
- 任务创建请求使用 Idempotency-Key。

## Task 对象

    {
      "id": "task_01...",
      "title": "检查项目测试",
      "instruction": "在允许目录中检查并运行测试，不要部署。",
      "target_device_id": "mac-studio",
      "adapter": "codex",
      "status": "queued",
      "created_at": "2026-10-23T00:00:00Z",
      "updated_at": "2026-10-23T00:00:00Z",
      "requires_approval": false,
      "summary": null,
      "result_ref": null,
      "error_code": null
    }

## 状态枚举

- queued
- accepted
- running
- needs_input
- succeeded
- failed
- cancelled
- unknown（状态无法可靠确定，需 reconciliation）

终态：succeeded、failed、cancelled。unknown 不是成功或失败的替代品。

## 已登记适配器发现

`GET /api/v1/capabilities`（需要用户令牌）

默认只返回 `dry-run`、目录 ID `demo`。当且仅当 Mac 本机 loopback、`AI_DESK_ENABLE_CODEX_READONLY=1` 且服务端配置了有效 Git 测试目录时，才返回 `codex-readonly`、目录 ID `codex-lab`。

服务端绝不把绝对目录路径传给移动界面。阶段一不允许外部 LAN 客户端调用真实 Codex 适配器。

## 手机端接口

### 创建任务
POST /api/v1/tasks

Headers:
- Authorization: Bearer <phone-token>
- Idempotency-Key: <unique-key>

Body:

    {
      "instruction": "检查指定项目并运行测试，不要部署",
      "target_device_id": "mac-studio",
      "adapter": "codex",
      "working_directory_id": "safe-project-01",
      "approval_mode": "confirm_high_risk"
    }

客户端提交允许目录 ID，不直接提交服务器路径；Coordinator 将 ID 映射为管理员配置的实际路径。

成功响应：

    {
      "accepted": true,
      "task": { "id": "task_01...", "status": "queued" }
    }

### 列出任务
GET /api/v1/tasks?status=running&limit=20

### 读取任务
GET /api/v1/tasks/{task_id}

### 读取任务事件
GET /api/v1/tasks/{task_id}/events?after={cursor}

### 取消任务
POST /api/v1/tasks/{task_id}/cancel

取消是尽力而为；若底层应用无法安全中止，必须返回实际状态，不能伪称已取消。

### 确认审批
POST /api/v1/tasks/{task_id}/approval

Body：

    { "decision": "approve", "approval_token": "single-use-token" }

审批令牌需短时有效、一次性使用，并绑定具体任务与操作摘要。

## Agent 接口

首选 Agent 主动连接 Coordinator，避免在每台 Mac 上开放未经认证的入站端口。

候选 WebSocket：
wss://<coordinator>/api/v1/agent-stream

Agent 消息类型：
- register
- heartbeat
- task.accepted
- task.progress
- task.needs_input
- task.result
- task.error

注册示例：

    {
      "type": "register",
      "device_id": "mac-studio",
      "display_name": "Mac Studio",
      "agent_version": "0.1.0",
      "capabilities": ["codex", "shell:allowlisted", "file-inspect"],
      "working_directory_ids": ["safe-project-01"]
    }

Capabilities 必须来自本机管理员配置，不得由远程用户请求临时扩大。

## 错误格式

    {
      "error": {
        "code": "TARGET_OFFLINE",
        "message": "目标设备当前离线",
        "retryable": true,
        "request_id": "req_..."
      }
    }

建议错误码：UNAUTHENTICATED、FORBIDDEN、INVALID_REQUEST、TARGET_OFFLINE、ADAPTER_UNAVAILABLE、APPROVAL_REQUIRED、TASK_NOT_FOUND、TASK_STATE_CONFLICT、RATE_LIMITED、INTERNAL_ERROR。

## 实时更新

MVP 可以先轮询任务详情；事件流稳定后再增加 SSE/WebSocket。必须保留 REST 查询作为恢复路径，不能依赖一个永不掉线的长连接。
