# 开发状态记录

更新日期：2026-10-23

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
- 任务事件审计轨迹测试： [run 39957078158](https://github.com/foxmuldery/ai-desk/actions/runs/39957078158) — success。

注意：各条 CI 对应不同 commit；应以最新 commit 对应的 workflow 结果作为最终验收。

## 当前限制

- 未在 Mac Studio 本机运行。
- 未在 S22 Ultra 实机验证 Typeless、通知、TTS。
- 手机与 Mac 的安全 LAN 通信尚未在真实设备上配置验证；UI/API 目前默认在本机 loopback 上验证。代码已要求 LAN 模式同时具备强 token 和 TLS 证书/私钥。
- 未实现真实 Codex adapter。
- 未实现多电脑 Agent 注册、心跳与任务分发。
- 未实现 Android 后台可靠通知或原生应用。
- 尚未完成全面安全审查。

## 下一步

1. 确认最新 CI 通过。
2. 增加服务层状态机与异常路径测试。
3. 在 Mac Studio 安全测试目录本地运行 dry-run。
4. 配置并实测手机信任的 TLS 证书，验证 S22 Ultra 到 Mac 的 LAN 通信；不将明文 HTTP 直接暴露到整个 LAN。
5. 在安全访问方案通过后，实测 S22 Ultra + Typeless。
6. 实现受控 Codex adapter。
7. 扩展多电脑执行代理。
