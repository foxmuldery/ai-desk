# AI Desk｜开发状态

更新：2026-10-25。以下内容明确区分：**已在 GitHub CI 验证**、**用户在 Mac Studio 本机确认**、**尚待 S22 Ultra 实机验收**。

## 已确认：Mac Studio 本机真实 Codex 只读调用

用户在 Mac Studio 上运行 `codex-cli 0.144.5`（ChatGPT 登录）并回报：

```text
PREFLIGHT_OK
GIT_UNCHANGED
CODEX_TURN_COMPLETED
SMOKE_OK
```

随后执行 `python3 scripts/smoke-coordinator-codex.py`，回报：

```text
COORDINATOR_SMOKE_START
GIT_UNCHANGED
COORDINATOR_SMOKE_OK
```

这证明已通过在 Mac Studio 上的 **Coordinator → SQLite 队列 → 只读 Codex 适配器 → 真实 Codex CLI → HTTP 状态/审计** 的单机实验。相关变更位于独立草稿 [PR #2](https://github.com/foxmuldery/ai-desk/pull/2)，[Issue #3](https://github.com/foxmuldery/ai-desk/issues/3) 已关闭。

**不代表**：任意代码修改权限、手机远程真实 Codex、多电脑任务调度或完整独立安全审计已通过。

## 本分支：手机安全 dry-run 联调（PR #6）

开发分支 `feat/phone-dry-run-tailnet` 基于 `main`，不包含真实 Codex 适配器代码。新增：

- `phone-dry-run` 执行 Profile；必须 loopback 绑定、至少 32 字符强令牌，且拒绝同时启用真实 Codex 标志。
- HTTP 任务提交与后台 worker 双重只允许 `dry-run`，重启恢复的非法历史任务也不能执行。
- 手机任务列表/详情/事件 API 不会暴露其它 adapter 的历史记录。
- 独立端口 `127.0.0.1:8766` 启动脚本，强随机临时 Bearer Token、独立 SQLite 文件。
- S22 Ultra 手机网页：核验 `phone-dry-run` Profile 和唯一 dry-run 能力；在提交前必须验证令牌；失败保留文字与幂等键；事件详情在自动刷新后保持打开；任务完成显示“模拟完成”；TTS 默认需用户开启。
- Tailscale Serve 私有 HTTPS 指引，不使用 Funnel、不改路由器、不开放公网端口。
- 脱敏的 Tailscale CLI 就绪检查 `scripts/check-phone-tailnet.sh`。
- HTTP、数据库隔离、代理头伪造、启动保护、Node 前端行为等自动化回归测试。

最新完整测试：[GitHub Actions 40157475717](https://github.com/foxmuldery/ai-desk/actions/runs/40157475717)，成功（更多后续提交应以最新 CI 为准）。

## 仍待真实设备验证

- Mac Studio 是否已安装、登录、能运行 Tailscale CLI。
- S22 Ultra 是否已安装、登录同一 tailnet、浏览器能打开由 Serve 提供的可信 HTTPS URL。
- 通过 Typeless 输入中文，提交 dry-run、观察 SQLite 状态与事件查询。
- 安卓浏览器前台语音播报、切到后台或锁屏时的行为。
- 其它电脑的 Agent 注册/心跳、应用跨设备执行。
- 远程真实 Codex 的项目级审批与独立安全复核；本分支**明确不开放**。

## 下一步

按 [PHONE_TAILNET_TEST.md](PHONE_TAILNET_TEST.md) 在 Mac Studio 安全准备，先运行：

```sh
cd "$HOME/AI-Desk-Phone-Test"
sh scripts/check-phone-tailnet.sh
```

只回传脱敏状态代码。确认 Tailscale 连接准备完毕后，独立启动 phone-dry-run，再进行 S22 Ultra 的网络、Typeless 和模拟任务验证。

涉及工作：[Issue #4](https://github.com/foxmuldery/ai-desk/issues/4)、[安全审查 Issue #5](https://github.com/foxmuldery/ai-desk/issues/5)、[手机 PR #6](https://github.com/foxmuldery/ai-desk/pull/6)。
