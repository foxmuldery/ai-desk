# 开发状态记录

更新日期：2026-10-24

## 当前版本

仓库： https://github.com/foxmuldery/ai-desk

当前实现是 **单机 dry-run MVP 骨架**。代码通过 GitHub Actions 的部分提交测试，但尚未在目标 Mac Studio 和 Samsung S22 Ultra 上现场运行，因此不能视为实机验收通过。

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

- 未在 Mac Studio 本机运行。
- 未在 S22 Ultra 实机验证 Typeless、通知、TTS；前台浏览器播报已写入代码，但真实浏览器自动播放策略仍需实测。
- 手机与 Mac 的安全 LAN 通信尚未在真实设备上配置验证；UI/API 目前默认在本机 loopback 上验证。代码已要求 LAN 模式同时具备强 token 和 TLS 证书/私钥。
- 只读 Codex CLI 适配器已在独立分支编码，默认关闭、仅本机可用；假 CLI 测试和 Mac Studio 实机测试尚待完成，不能称为真实任务已成功运行。
- 未实现多电脑 Agent 注册、心跳与任务分发。
- 未实现 Android 后台可靠通知或原生应用。
- 尚未完成全面安全审查。

## 下一步

1. 确认最新 CI 通过。
2. 增加服务层状态机与异常路径测试。
3. 在 Mac Studio 安全测试目录本地运行 dry-run。
4. 配置并实测手机信任的 TLS 证书，验证 S22 Ultra 到 Mac 的 LAN 通信；不将明文 HTTP 直接暴露到整个 LAN。
5. 在安全访问方案通过后，实测 S22 Ultra + Typeless。
6. 按 docs/CODEX_LOCAL_TEST.md 实测并验收受控 Codex CLI 只读适配器。
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
