# Work / Codex Desktop 交接说明

## 项目入口

仓库： https://github.com/foxmuldery/ai-desk

从 README 和以下文档开始：
1. docs/ARCHITECTURE.md
2. docs/ROADMAP.md
3. docs/API.md
4. docs/ANDROID_CLIENT.md
5. docs/MAC_AGENT.md
6. docs/APP_ADAPTERS.md
7. docs/SECURITY.md
8. docs/ACCEPTANCE_TESTS.md

## 当前已确认的产品决定

- 项目名：AI Desk / AI 总机。
- 用户希望复用闲置设备，优先零新增硬件。
- 手机：Samsung Galaxy S22 Ultra。
- 已安装 Typeless，第一版通过文本输入框使用它进行语音转文字；不假设存在公开 API。
- 路由器：Linksys Velop MX5300，明确禁止刷机，保持原厂固件。
- Mac Studio 暂时作为 Coordinator。
- 后续接入多台 Mac，并让同一套任务系统支持 Codex 与其他应用。
- 用户希望之后可以切换到 Work 模式继续开发。
- 不采购 ATA、IP 电话机、录音盒或其他专用硬件，除非之后有明确必要且经过用户确认。

## 重要的实现约束

1. 先实现单机闭环，再做多电脑。
2. 先做手机 Web/PWA 验证，再决定是否开发原生 Android 客户端。
3. Typeless 只当作用户可操作的语音键盘；不得依赖自动打开、后台监听或未确认的 API。
4. 所有远程操作经适配器、参数校验、目录白名单和权限检查。
5. 不向 LAN 或公网开放无认证的任意命令执行端点。
6. Coordinator 先持久化任务，再向客户端确认已接收。
7. 执行状态不明时显示 unknown，不能误报成功。
8. 删除、覆盖原始资产、部署、发布、外部发送等高风险动作必须经过审批。
9. 路由器不刷机、不承载服务。
10. 不提交真实 IP、网络拓扑、私人目录、token 或项目机密。

## 开始开发前的现场盘点

在目标 Mac Studio 上只读检查并记录：
- macOS 版本与芯片架构。
- Codex CLI/SDK 当前版本和官方可用的非交互执行方式。
- Git、语言运行时和包管理器版本。
- 当前用户权限与可用的开机自启机制。
- 一个可安全测试的项目目录。
- Mac Studio 在 LAN 的连接方式与可达性。
- S22 Ultra 的 Android 版本、浏览器、Typeless 键盘是否可用。
- 当前 MX5300 固件保持不变。

不要在盘点阶段改路由器、安装全局依赖、修改现有 Codex 配置或对生产项目运行写操作。

## 建议的第一张开发任务

标题：Build single-machine dry-run MVP

范围：
- 先选定最容易维护的服务端技术栈。
- 创建 Coordinator、SQLite schema、任务状态机和简单手机页面。
- 实现 dry-run adapter，先验证任务创建、排队、状态事件和结果显示。
- 增加认证、目录 ID 校验和幂等键。
- 增加单元测试与 API 集成测试。
- 暂时不执行任意 shell、不调用真实 Codex、不做公网访问。
- 在验收通过后，再实现真实 Codex adapter。

交付必须包括：
- 实际代码和运行说明。
- 自动化测试结果。
- 已知限制与安全边界。
- 在 S22 Ultra 上的真实设备验证记录（未测就明确标注未测）。
- 更新本文件与 README 的阶段状态。

## 当前状态（2026-10-24）

已提交：
- Python 标准库 HTTP Coordinator。
- SQLite 任务存储、事件历史、幂等键及冲突校验。
- 状态转换规则，阻止终态任务被重新打开。
- 背景 worker 队列；dry-run 任务不会阻塞 HTTP 请求。
- 只允许 dry-run 的适配器注册表；不执行 shell/Codex 命令。
- 手机优先的静态 Web UI，支持输入任务、token、提交、查看任务和事件。
- 本地启动脚本、环境变量示例、单元测试、HTTP 集成测试。
- GitHub Actions 测试工作流；多个近期 CI 运行已通过。
- 当前状态和证据见 docs/DEV_STATUS.md。
- 研发 Issue： https://github.com/foxmuldery/ai-desk/issues/1

尚未验证：
- GitHub Actions 首轮运行已排队，但尚未开始/完成，不能声称测试通过。
- 未在 Mac Studio 本机运行。
- 未在 S22 Ultra 实机验证 Typeless、通知、TTS。
- 当前 Web UI 默认只适用于 Coordinator 所在电脑的 loopback 地址。代码已要求非 loopback 绑定必须有强 token 与 TLS 证书/私钥，但手机信任证书及跨设备访问尚未实测。
- 已在独立分支开发只读 Codex CLI 适配器：需 Mac Studio 实机 CLI 参数和 ChatGPT 登录态验收，默认关闭且拒绝来自 LAN 的真实 Codex 调用。多电脑 Agent、后台 Android 通知和安全 LAN 手机连接尚未完成。

下一步：
1. 确认最新 GitHub Actions 运行通过；历史失败提交已被后续测试修复。
2. 继续代码审查，补异常路径、重启恢复和 API 状态测试。
3. 在 Mac Studio 的安全测试目录运行 dry-run MVP。
4. 在完成认证和安全传输设计后，再让 S22 Ultra 通过局域网访问。
5. 按 docs/CODEX_LOCAL_TEST.md 实机验收已经受控的只读 Codex 适配器；通过后才规划写入权限和审批功能。


## 并行开发工作线（2026-10-24）

- [PR #2：Codex CLI 只读适配器](https://github.com/foxmuldery/ai-desk/pull/2)：代码与假 CLI 测试已经提交，**仍是 Draft，尚未合并主分支**。
- [Issue #3：Mac Studio 实机 smoke test](https://github.com/foxmuldery/ai-desk/issues/3)：需要 Mac Studio 本机执行 `docs/CODEX_LOCAL_TEST.md`。
- [Issue #4：S22 Ultra 安全 LAN 与 Typeless](https://github.com/foxmuldery/ai-desk/issues/4)：只准先用 dry-run，暂不远程执行真实 Codex。
- [Issue #5：Codex 适配器独立安全审查](https://github.com/foxmuldery/ai-desk/issues/5)：评估 sandbox、认证、环境、超时、输出、崩溃恢复。

如由 Work 或另一个 Codex Agent 接手，请先阅读目标任务的范围和安全边界，再对分支实际运行测试。不要声称已启动子代理；当前只是准备好可独立领取的任务。
