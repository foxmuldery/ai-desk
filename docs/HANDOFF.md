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

## 当前状态

本仓库目前完成的是设计与交接文档首轮提交，尚无可运行应用、尚无端到端测试、尚未验证真实设备兼容性。不要把文档规划描述为已经实现。
