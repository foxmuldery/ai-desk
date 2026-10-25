# 开发状态记录

更新日期：2026-10-25

## 当前版本

仓库： https://github.com/foxmuldery/ai-desk

当前实现是 **单机 dry-run Coordinator + 实验性 Codex CLI 只读适配器**。截至 2026-10-25，Mac Studio 上 CLI-only 与 Coordinator→真实 Codex 的本机只读 smoke 已获用户终端 PASS 回报；S22 Ultra 的安全 HTTPS 派单、Typeless 和锁屏通知尚未实机验证。此结果不能代表手机远程闭环已经完成。

## 已实现

- Python 标准库 HTTP Coordinator。
- SQLite 任务与事件存储。
- 幂等键去重；同一 key 被用于不同请求时返回 409。
- 任务状态转换限制；终态任务不能重新打开。
- 背景 worker 队列；HTTP 请求可在任务执行前返回 queued。
- 服务重启时恢复 queued 任务；把上次运行中遗留的 accepted/running 任务标记为 unknown，要求核对而不是盲目重跑。
- Dry-run adapter 白名单：只生成模拟结果，不执行 shell、Codex 或其他应用。
- 手机优先的静态网页界面，可提交任务、查看列表和事件。
- 本地启动脚本、环境示例、单元测试、HTTP 集成测试、GitHub Actions。
- 安全默认：Coordinator 默认绑定 127.0.0.1；非 loopback 绑定要求至少 32 字符 token + TLS 证书/私钥。

## 已验证的 CI 证据

- 基础 Python 单元测试与编译： [run 39916081195](https://github.com/foxmuldery/ai-desk/actions/runs/39916081195) — success。
- 幂等冲突与 HTTP 集成测试： [run 39956725929](https://github.com/foxmuldery/ai-desk/actions/runs/39956725929) — success。
- 状态转换测试： [run 39956693179](https://github.com/foxmuldery/ai-desk/actions/runs/39956693179) — success。
- 背景任务生命周期： [run 39956852474](https://github.com/foxmuldery/ai-desk/actions/runs/39956852474) — success。
- 背景任务生命周期： [run 39956852474](https://github.com/foxmuldery/ai-desk/actions/runs/39956852474) — success。
- Worker 异常保护： [run 39956923150](https://github.com/foxmuldery/ai-desk/actions/runs/39956923150) — success。
- 安全响应头与非 loopback 强令牌限制： [run 39957059833](https://github.com/foxmuldery/ai-desk/actions/runs/39957059833) — success。
- 非 loopback 缺少 TLS 时拒绝启动： [run 39957232995](https://github.com/foxmuldery/ai-desk/actions/runs/39957232995) — success。
- 启动脚本区分 loopback HTTP 与 LAN HTTPS： [run 39957330535](https://github.com/foxmuldery/ai-desk/actions/runs/39957330535) — success。
- 静态资源安全头与 CSP 集成测试： [run 39957569052](https://github.com/foxmuldery/ai-desk/actions/runs/39957569052) — success。
- 前端 JavaScript 语法检查： [run 39957583178](https://github.com/foxmuldery/ai-desk/actions/runs/39957583178) — success。
- 任务事件审计轨迹测试： [run 39957078158](https://github.com/foxmuldery/ai-desk/actions/runs/39957078158) — success。

注意：各条 CI 对应不同 commit；应以最新 commit 对应的 workflow 结果作为最终验收。

## 当前限制

- 已在 Mac Studio 本机完成 CLI-only 与 Coordinator→Codex 的只读集成烟雾测试（2026-10-25，用户终端报告 `SMOKE_OK` 和 `COORDINATOR_SMOKE_OK`）；尚未进行 Android 远程联调。
- 未在 S22 Ultra 实机验证 Typeless、通知、TTS；前台浏览器播报已写入代码，但真实浏览器自动播放策略仍需实测。
- 手机与 Mac 的安全 LAN 通信尚未在真实设备上配置验证；UI/API 目前默认在本机 loopback 上验证。代码已要求 LAN 模式同时具备强 token 和 TLS 证书/私钥。
- 只读 Codex CLI 适配器已在独立分支实现，默认关闭、仅本机可用；Mac Studio 实机只读任务和 Coordinator 本机调度测试已通过，未开放手机远程真实执行。
- 未实现多电脑 Agent 注册、心跳与任务分发。
- 未实现 Android 后台可靠通知或原生应用。
- 尚未完成全面安全审查。

## 下一步

1. 确认最新 CI 通过。
2. 增加服务层状态机与异常路径测试。
3. 在 Mac Studio 安全测试目录本地运行 dry-run。
4. 配置并实测手机信任的 TLS 证书，验证 S22 Ultra 到 Mac 的 LAN 通信；不将明文 HTTP 直接暴露到整个 LAN。
5. 在安全访问方案通过后，实测 S22 Ultra + Typeless。
6. Mac Studio 本机受控 Codex 只读集成测试已通过；接下来独立完成安全审查与局域网 dry-run 手机验收，不能直接开放远程 Codex。
7. 扩展多电脑执行代理。

## 2026-10-24：受控 Codex CLI 只读适配器（独立草稿 PR）

- 开发分支：`feat/codex-readonly-adapter`
- 草稿 PR：[PR #2](https://github.com/foxmuldery/ai-desk/pull/2)
- 最新分支 CI：[GitHub Actions](https://github.com/foxmuldery/ai-desk/actions/runs/40071724759) — 24 项自动化测试通过；Python 编译、前端语法、Shell 语法检查通过。
- 已实现并默认关闭：`codex-readonly` 适配器、`codex-lab` Git 测试目录白名单、本地非交互 Codex CLI 调用、JSONL 结束事件验收、执行超时与失败反馈。
- 安全边界：只在 loopback 可用；非 loopback + Codex 同时启用时拒绝启动；隔离传给 Codex 子进程的环境变量，避免继承 AI Desk bearer token。
- 测试使用隔离假 CLI，无需 ChatGPT 认证或网络；这不代表真实 Codex 在 Mac Studio 已执行成功。
- Mac Studio 实机验证：[Issue #3](https://github.com/foxmuldery/ai-desk/issues/3)
- S22 Ultra + Typeless 安全连接：[Issue #4](https://github.com/foxmuldery/ai-desk/issues/4)
- 独立安全复核：[Issue #5](https://github.com/foxmuldery/ai-desk/issues/5)

**尚未完成**：在目标 Mac Studio 上验证用户报告的 `codex-cli 0.144.5` 对参数的实际支持、复用 ChatGPT 登录、真实只读命令和结果；手机到 Mac 的真实执行链路仍未开放。

## 2026-10-24：只读实机烟雾测试脚本

- 新增 `scripts/smoke-codex-readonly.sh`：仅针对 `$HOME/AI-Desk-Sandbox` 独立 Git 测试仓库调用一次真实 Codex CLI。
- 执行时显示脱敏状态；同时校验零退出码、`turn.completed` 事件、非空最终回复，以及前后 Git 状态与 README 校验值不变。
- 额外假 CLI 测试覆盖成功、非零退出、缺少完成事件和测试文件被修改。
- 最新执行：[GitHub Actions 40073339517](https://github.com/foxmuldery/ai-desk/actions/runs/40073339517) — **28 项测试通过**，包括 Python 编译、JavaScript 与 shell 语法检查。
- 真实 Mac Studio 尚未运行此脚本；需按 `docs/CODEX_LOCAL_TEST.md` 操作，并只回传 `PREFLIGHT_OK / SMOKE_OK / SMOKE_FAIL` 脱敏状态。

## 2026-10-24：真实 CLI smoke 通过；Coordinator smoke 待实机验收

用户在 Mac Studio 原生终端提供以下结果：

```text
GIT_UNCHANGED
CODEX_TURN_COMPLETED
SMOKE_OK: real Codex read-only CLI turn completed; lab Git state unchanged.
```

这确认 Mac Studio 上真实 `codex-cli 0.144.5` 与现有 ChatGPT 登录可完成一次只读 `codex exec` 任务，脚本所检查的独立 Git 测试仓库状态及 README 摘要没有变化。该证据由用户终端提供，**不能替代 AI Desk Coordinator 调度验收**。

本次额外实现：

- `scripts/smoke-coordinator-codex.py`：只在 `127.0.0.1` 启动临时 Coordinator、随机令牌和 SQLite 数据库，从 HTTP API 发送一条 `codex-readonly` 任务，验证真实执行器成功以及 `adapter.result` 审计事件，然后删除临时数据库并核对测试仓库没有变化。
- `tests/test_coordinator_smoke.py`：三个隔离假 CLI 场景（正常完成、失败事件、测试仓库被修改）。
- [GitHub Actions 40077097985](https://github.com/foxmuldery/ai-desk/actions/runs/40077097985)：**31 项自动化测试通过**，仍不等于 Mac Studio 上 Coordinator 联调通过。
- Mac 实机下一步：在已克隆的功能分支执行 `git pull --ff-only`，运行 `python3 scripts/smoke-coordinator-codex.py`，只回传 `COORDINATOR_SMOKE_OK` 或脱敏错误码。

仍未完成：真实手机 S22 Ultra → Mac Studio 的 HTTPS 派单、手机锁屏通知、Codex 写入权限审批、多 Mac Agent。仍然默认不开放真实 Codex 的局域网访问。

## 2026-10-25：Mac Studio Coordinator → Codex 真实本机闭环通过

**来源：用户提供的 Mac Studio 原生终端输出；未经远程独立观察。**

```text
COORDINATOR_SMOKE_START: loopback-only service with temporary database
Only the isolated lab is used. No task details or tokens will be printed.
GIT_UNCHANGED
COORDINATOR_SMOKE_OK
```

- 已先通过独立 `codex exec` 只读 smoke（`PREFLIGHT_OK`、`CODEX_TURN_COMPLETED`、`SMOKE_OK`）。
- 此次使用 `scripts/smoke-coordinator-codex.py`，从 `127.0.0.1` HTTP API 提交任务，经临时 SQLite 队列与 `codex-readonly` 执行器调用 Mac Studio 上已登录的真实 Codex，再读取任务成功状态和 `adapter.result` 审计事件。
- 脚本复核隔离测试仓库 Git 状态及 README 校验值没有变化，并清理临时 Coordinator 与数据库。
- 测试脚本的成功结论仅覆盖独立无敏感信息 Git lab 的本机只读执行，不证明所有项目、任意工作目录、任何写操作或手机远程执行安全。
- 此里程碑对应 [Issue #3](https://github.com/foxmuldery/ai-desk/issues/3)；[PR #2](https://github.com/foxmuldery/ai-desk/pull/2) 仍保持草稿，等待独立 [安全审查 #5](https://github.com/foxmuldery/ai-desk/issues/5)。

**接下来的验收目标**：S22 Ultra + Typeless → 经过可信 HTTPS/认证的 Mac Studio AI Desk → `dry-run` → 手机查询结果。真实 Codex 仍不暴露给手机或 LAN，写权限和多 Mac Agent 留待后续。
