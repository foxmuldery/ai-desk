# AI Desk｜AI 总机

将闲置的 Samsung Galaxy S22 Ultra 变成多电脑 AI 工作控制台：通过 Typeless 语音输入任务，统一调度多台 Mac 上的 Codex 与其他应用，并在任务完成、失败或需要决策时通知手机、播报结果。

> **当前阶段：单机 dry-run MVP 骨架已提交，尚待 CI 与真实设备验证。** 目前可以启动本地 HTTP 服务和手机网页界面；任务只经过 dry-run 适配器，不会执行 Codex、shell 或其他应用。

## 已确定的原则

- **零新增硬件优先**：复用 S22 Ultra、现有 Mac 和 Linksys MX5300。
- **路由器不刷机**：MX5300 保持原厂固件，仅承担现有网络与 Wi-Fi 功能。
- **Mac Studio 暂任调度中心**：先打通单机闭环，之后再接入其他 Mac。
- **Typeless 负责语音输入**：第一版使用文本输入框工作流，不依赖未经确认的 Typeless API。
- **跨应用设计**：Codex 是第一种执行适配器；之后按需求增加浏览器、命令行、Blender、媒体处理等适配器。
- **先可靠后智能**：任务状态持久化、权限控制、可追踪日志和明确验收优先于复杂语音 Agent。
- **诚实报告结果**：只有任务执行器和验收条件均确认成功时才标记为成功。

## 目标架构

```mermaid
flowchart TD
  P[Samsung S22 Ultra<br/>AI Desk Web UI / Typeless] <-->|HTTPS / WebSocket| C[Mac Studio<br/>AI Desk Coordinator]
  C <--> DB[(SQLite task store)]
  C <--> N[Notification and TTS events]
  C <--> A[Application adapter registry]
  C <-->|Authenticated agent channel| S[Mac Studio Agent]
  C <-->|Authenticated agent channel| M[Mac mini Agent]
  C <-->|Authenticated agent channel| B[MacBook / other Mac agents]
  S --> X1[Codex CLI / scripts / local apps]
  M --> X2[Codex CLI / tests / browser tools]
  B --> X3[Approved app adapters]
  N --> P
  R[Linksys MX5300<br/>stock firmware; LAN only] --- P
  R --- C
  R --- S
  R --- M
  R --- B
```

## 第一版（MVP）范围

1. 在 Mac Studio 启动本地调度服务。
2. 提供适合 S22 Ultra 的手机网页界面：任务输入、目标电脑选择、任务列表和详情。
3. 通过 Typeless 将语音输入转成文字；用户检查后提交。
4. 调度服务持久化任务，并调用 Mac Studio 本机的受控 Codex 适配器。
5. 把真实执行状态、结果摘要和错误反馈给手机。
6. Android 端通过通知、提示音和系统中文 TTS 汇报。
7. 具备最基本的认证、允许目录、危险操作审批和任务审计。

## 非目标（MVP 不做）

- 不刷 Linksys MX5300 固件。
- 不购买 ATA、IP 电话、录音盒或其他专用硬件。
- 不要求路由器运行自定义服务。
- 不假设 Typeless 提供公开 API、后台唤醒或自动化控制能力。
- 不通过任意命令字符串开放无限制远程 shell。
- 不自动执行未授权的删除、外部发布、部署、购买或账号权限变更。
- 不承诺手机在任何 Android 省电设置下都能保证后台通知；需在真实设备上测试。

## 研发路线

| 阶段 | 交付 | 验收重点 |
|---|---|---|
| 0. 规格与安全边界 | 本仓库设计文档、接口草案、验收清单 | 范围与风险明确 |
| 1. 单机闭环 | 手机 UI + Mac Studio coordinator + Codex adapter | 提交、执行、真实状态、结果通知 |
| 2. 稳定性 | SQLite 持久化、重启恢复、日志、权限 | 不丢任务、不伪报成功 |
| 3. 多电脑 | macOS agent 注册、心跳、任务分派 | 在线状态、排队、断线恢复 |
| 4. 多应用 | adapter registry 与首批应用适配器 | 每种适配器单独验收 |
| 5. Android 强化 | PWA 评估结果后决定是否原生封装 | 锁屏通知、TTS、后台行为 |

详细计划见 [docs/ROADMAP.md](docs/ROADMAP.md)。

## 本地运行（dry-run）

要求：Python 3.11 或更新版本，无第三方 Python 依赖。

在仓库根目录执行：

```sh
sh scripts/run-local.sh
```

脚本会生成临时 bearer token 并打印到终端，复制该 token 后在同一台 Mac 上打开 `http://127.0.0.1:8765`，输入令牌后即可提交 dry-run 测试任务。数据默认保存在 `data/ai-desk.sqlite3`。

默认只绑定 `127.0.0.1`，所以手机不能直接访问这个地址。要让 S22 Ultra 访问，下一步必须先设计并验证受保护的局域网传输方式；不要简单把当前明文 HTTP 服务暴露到整个 LAN 或互联网。当前 UI 在页面前台可使用浏览器语音合成；后台通知尚未实现。

运行测试：

```sh
PYTHONPATH=server python3 -m unittest discover -s tests -v
PYTHONPATH=server python3 -m compileall -q server tests
```

当前 dry-run 是模拟执行，用于验证任务存储与 UI，不是 Codex 执行器。

## 当前实现状态

已具备单机 dry-run Coordinator、SQLite 任务记录、背景队列、幂等键保护、手机优先网页界面及测试。当前仍未接入真实 Codex，也未完成手机到 Mac 的安全 LAN 通信和 S22 Ultra 实机验证。请查看 [docs/DEV_STATUS.md](docs/DEV_STATUS.md) 获取逐项状态与 CI 证据。

## 文档索引

- [当前开发状态与 CI 证据](docs/DEV_STATUS.md)
- [系统架构](docs/ARCHITECTURE.md)
- [研发路线与里程碑](docs/ROADMAP.md)
- [API 草案](docs/API.md)
- [Android / S22 Ultra 交互方案](docs/ANDROID_CLIENT.md)
- [Mac 执行代理](docs/MAC_AGENT.md)
- [应用适配器设计](docs/APP_ADAPTERS.md)
- [安全与权限](docs/SECURITY.md)
- [测试与验收清单](docs/ACCEPTANCE_TESTS.md)
- [Work / Codex Desktop 交接说明](docs/HANDOFF.md)

## 当前设备与假设

- 手机：Samsung Galaxy S22 Ultra（Android 版本待现场确认）。
- 语音输入：已安装 Typeless；通过系统键盘工作流输入文本。
- 网络：Linksys Velop MX5300，明确保持原厂固件。
- 调度主机：Mac Studio（macOS 版本、固定地址与现有运行环境待确认）。
- 执行节点：Mac Studio 优先；其他 Mac 的实际型号、主机名、项目路径、权限待登记。
- Codex：需在目标 Mac 上确认实际 CLI/SDK 安装方式和允许的执行模式后实现适配器。

## 开发状态

当前只完成设计文档的首轮落库。尚未完成：可运行代码、端到端测试、真实设备安装、Typeless 兼容性验证、Codex 适配器验证和多电脑测试。后续开发应以验收证据更新状态，不以文档存在代替功能完成。

## 安全提示

本服务会触发本机应用和代码执行，因此默认只绑定到可信局域网接口，要求认证，限制工作目录，记录审计日志；不应将调度端口直接暴露到互联网。跨网络访问需要另行设计安全的 VPN 或经过认证的远程入口。
