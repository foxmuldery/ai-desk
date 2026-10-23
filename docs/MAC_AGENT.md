# macOS 执行代理

## 目标

让 Mac Studio、Mac mini、MacBook 等设备以统一协议接收受控任务，并在本机调用 Codex 或其他允许的应用适配器。执行代理不是开放式远程 shell。

## 单机起步

第一阶段可在 Mac Studio 同机运行 Coordinator 和 Agent，但逻辑上保持分离：
- Coordinator：HTTP API、任务状态、SQLite、通知事件。
- Agent：适配器运行、日志采集、结果验收。
- Local transport：仅限本机或经过认证的内部通道。

## 节点身份与配置

每台电脑需要管理员创建的配置：
- device_id：稳定且唯一。
- display_name：例如 Mac Studio。
- agent_version。
- allowed_adapter_ids。
- working_directory_ids 到本地路径的映射。
- 并发上限。
- 允许执行的环境变量白名单。
- 心跳周期与失联阈值。

禁止客户端自行传入任意文件系统路径、任意二进制路径或环境变量覆盖。

## 任务执行协议

1. Agent 接收任务后，校验 task ID、适配器 ID、参数 schema 和允许目录。
2. Agent 记录本地执行开始事件。
3. 适配器使用明确的参数数组启动，不拼接不可信 shell 字符串。
4. 采集 stdout/stderr 时需限制大小并过滤凭据。
5. 执行器报告退出码、摘要、验收证据和输出文件引用。
6. Coordinator 持久化最终状态与事件。
7. 失败或中断时保留诊断信息，不自动无限重试。

## Codex 适配器

实现前核实目标 Mac 上实际安装的 Codex CLI/SDK 版本、官方支持的调用方式、认证状态、执行审批模式与沙箱行为。不要假设所有机器版本相同，也不要把交互式桌面会话的权限直接继承给远程请求。

适配器应接收：instruction、working_directory_id、approval_policy、timeout_seconds、task_id / correlation_id。

适配器应返回：execution_status、exit_code（如果接口提供）、summary、event stream/log reference、verification results、artifacts references。

不应返回 API token、cookie、环境变量秘密、未经用户授权的完整个人文件内容、无关的完整日志或大文件正文。

## 应用执行隔离

- 允许目录外的读写默认拒绝。
- 每个适配器声明需要的权限。
- 删除、部署、发布、外部消息发送等动作必须走审批策略。
- 不使用管理员/root 权限作为默认运行方式。
- 对可重复执行任务设置幂等策略。
- Agent 重启后把未能确认的任务标记为 unknown，等待协调端核对。

## 可观测性

记录 task_id、device_id、adapter_id、时间戳、状态变化、耗时、退出状态、验收结果、错误码和重试原因。

避免记录认证秘密、完整访问令牌、与任务无关的用户内容，以及未过滤的敏感 stdout/stderr。
