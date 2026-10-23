# 系统架构

## 1. 架构决策

- Linksys MX5300 保持原厂固件，只承担 LAN/Wi-Fi。
- Mac Studio 是首版常驻协调主机。
- Android S22 Ultra 是控制面板；Typeless 作为语音转文字输入方式，不假设它有可供本项目调用的程序 API。
- 任务执行发生在 Mac 本机。调度服务负责分发与状态，不向手机开放任意 shell。
- 首版采用手机网页/PWA 验证交互；只有真实设备测试证明 PWA 无法满足通知/后台需求时，才评估原生 Android 客户端。

## 2. 逻辑组件

1. Mobile UI：任务输入、目标设备、任务列表与详情。
2. Coordinator API：认证、请求校验、任务状态机、任务队列、事件查询。
3. SQLite Store：任务、设备、任务事件、执行记录、幂等键。
4. Agent Registry：设备注册、能力清单、心跳、连接状态。
5. Dispatcher：根据目标设备、应用能力与节点状态分配任务。
6. Adapter Registry：受控适配器，例如 Codex CLI、测试脚本、文件处理。
7. Agent Runtime：每台 Mac 的本机执行器，只允许已登记的适配器和目录。
8. Notification/TTS：将事件摘要交给手机；前端或 Android 系统负责播报。

## 3. 数据流

### 提交任务
1. 用户在 S22 Ultra 打开 AI Desk。
2. 在输入框调用 Typeless，生成文字。
3. 用户确认文字、目标电脑和操作边界。
4. UI 发送带幂等键的创建任务请求。
5. Coordinator 验证认证、目标、适配器和权限。
6. 任务写入 SQLite 后才返回“已接收”。
7. Dispatcher 向在线 Agent 发送任务。
8. Agent 接收后回报 accepted/running 事件。

### 执行与结果
1. Agent 依据适配器 ID 和经过校验的参数启动适配器。
2. 输出以事件形式回传，敏感内容需过滤。
3. 适配器返回退出状态、结构化结果和验收证据。
4. Coordinator 按状态机更新任务并保存事件。
5. 只有执行与验收条件满足，任务才可标记 succeeded。
6. 手机查询任务状态或接收事件；必要时发系统通知。
7. 用户打开通知，查看报告或播放系统 TTS。

## 4. 部署阶段

### Phase 1：单机
同一个 Mac Studio 上运行 Coordinator、SQLite 和本机 Agent。可以先同主机部署，但保持模块边界清晰。

### Phase 2：多电脑
Coordinator 仍运行在 Mac Studio；每台远端 Mac 运行 Agent，通过认证的主动连接或安全 WebSocket 通道接入。避免为 Agent 开放无认证的入站命令端口。

### Phase 3：扩展应用
通过注册适配器能力扩展，不让 Coordinator 接受任意命令文本。每个适配器需要参数 schema、权限声明、超时和验收方式。

## 5. 网络与可靠性

- 默认只在可信 LAN 上监听；生产实现需显式配置 bind address。
- 为任务创建接口加入幂等键，防止重复点击产生重复执行。
- 任务先持久化再确认收到。
- Agent 使用 heartbeat 与 last_seen 判断在线，不将心跳丢失误报为任务失败。
- Coordinator 重启后恢复数据库中的任务；对执行中断任务标记为 unknown/reconciliation_required，核对 Agent 后再决定是否重试。
- 不自动重跑非幂等任务。
- 手机离线不影响已接收任务；重新打开后从 Coordinator 拉取状态。

## 6. 选型建议

首版优先选择开发与运维成本低的实现；具体语言/框架在开始写代码时按 Mac 环境和可维护性确认。SQLite 足够支撑首版，不需要先引入消息队列或 Kubernetes。
