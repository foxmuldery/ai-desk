# AI Desk：真实 Codex CLI 只读检查验收

更新：2026-10-24。当前目标是首次在 **Mac Studio 本机**调用现有 ChatGPT 登录态的 Codex CLI。
此阶段仍不允许手机或局域网中的其他设备直接触发真实 Codex，也不执行代码修改。

## 已知信息

用户提供的本机输出：

```text
codex-cli 0.144.5
Logged in using ChatGPT
```

说明 CLI 已安装且该交互用户登录了 ChatGPT；不需要把 token、Cookie 或 API Key 交给 AI Desk。

## 安全边界

- `AI_DESK_ENABLE_CODEX_READONLY` 默认关闭。
- 真正的 CLI 适配器仅在 Coordinator 绑定 loopback 时可用；若启用 Codex 却尝试绑定非 loopback 地址，服务直接拒绝启动。
- 只能使用服务端预先设置的绝对路径 `AI_DESK_CODEX_READONLY_ROOT`，对应唯一目录 ID `codex-lab`。
- 该目录必须已经是 Git 仓库；手机/HTTP 请求不能提供真实目录路径。
- 用参数数组调用本机 Codex CLI；用户自然语言经 stdin 而非 shell 解释。
- CLI 显式传入 `--sandbox read-only`、`--ask-for-approval never`、`--ignore-user-config`、`--ephemeral`。
- 不使用 `--skip-git-repo-check`、`--yolo` 或 `danger-full-access`。
- 仅在 CLI 返回零退出码、JSONL 包含 `turn.completed`、最终消息非空时标记为成功。
- 失败、超时、异常均不会返回“已完成”的状态；原始 stderr 和 JSONL 事件不会直接发送到手机。
- 只读沙箱主要用于限制写操作，不等于秘密数据隔离；不要把私人素材或未授权凭据放在测试目录，使用专用测试仓库。

## 用户现在可以提前准备（Mac Studio）

在终端执行：

```sh
mkdir -p "$HOME/AI-Desk-Sandbox"
cd "$HOME/AI-Desk-Sandbox"
git init
printf "AI Desk independent read-only test repository.\n" > README.md
codex exec --help
```

这些命令不会启动推理任务。检查帮助中是否包含 `--sandbox`、`--json`、`--output-last-message`、`--ignore-user-config`、`--ephemeral`。如果版本不支持某个参数，先反馈帮助信息，不要为了测试强行修改 Codex 配置或升级。

克隆仓库后，还可以用项目提供的无副作用预检脚本一次检查这些条件：

```sh
sh scripts/check-codex.sh
```

脚本只读取 CLI 版本、登录状态、帮助信息和测试目录状态；不会执行 AI 任务。不要分享任何认证数据。

## 下一项：真实 Codex CLI 只读烟雾测试（现在即可执行）

帮助菜单可正常显示后，先不要启动 AI Desk 服务。请在 Mac Studio 上使用独立目录克隆草稿 PR 的功能分支：

```sh
git clone --single-branch --branch feat/codex-readonly-adapter \
  https://github.com/foxmuldery/ai-desk.git "$HOME/AI-Desk-CLI-Test"
cd "$HOME/AI-Desk-CLI-Test"
sh scripts/check-codex.sh
sh scripts/smoke-codex-readonly.sh
```

**只需回传结果标志**：`PREFLIGHT_OK`、`SMOKE_OK`、`SMOKE_FAIL`、`CODEX_EXIT_...` 或 `PREFLIGHT_FAIL`。不要发送原始 Codex JSONL、错误日志、凭据、token 或个人文件内容。脚本执行完后会清理保存在临时目录的事件与输出，仅向终端显示脱敏状态。

这个 smoke test 会对`$HOME/AI-Desk-Sandbox`中的无敏感信息 README 运行一次真实 Codex，只读沙箱禁止对工作区写入，脚本还会比较 README 的 SHA-256 和 Git 状态。它需要 Codex 当前登录态可联网，可能使用模型额度。测试程序不会将你的既有影视、游戏工作目录设为工作区。

如果`$HOME/AI-Desk-CLI-Test`已经存在，请勿覆盖已有文件；改用不同的空目录或在现有克隆中检查分支后再运行。

## Mac Studio：AI Desk Coordinator → 真实 Codex 本地闭环（CLI smoke 成功后）

在已经获得 `SMOKE_OK`、`CODEX_TURN_COMPLETED`、`GIT_UNCHANGED` 后，可以验证调度层，而不是重复直接调用 CLI。

下述命令**仅在 Mac Studio 本机终端**执行，使用已经存在的功能分支克隆，无需 API Key：

```sh
cd "$HOME/AI-Desk-CLI-Test"
git pull --ff-only
python3 scripts/smoke-coordinator-codex.py
```

该脚本会：

1. 检查仅包含无敏感内容的 `$HOME/AI-Desk-Sandbox` Git 测试仓库；
2. 创建一个临时数据库和随机访问令牌，只在 `127.0.0.1` 启动 Coordinator；
3. 通过需要令牌的 HTTP API 查询 `codex-readonly` 能力，并提交一条读取 README 的测试任务；
4. 由 Coordinator 后台队列调用受控的 `codex-readonly` 适配器，通过现有 ChatGPT 登录完成非交互回合；
5. 轮询最终任务状态并检查 `adapter.result` 审计事件；
6. 停止临时 Coordinator、清理临时数据，复核 README 的 SHA-256 和 Git 状态没有变化。

成功时只显示 `GIT_UNCHANGED` 和 `COORDINATOR_SMOKE_OK`。失败时显示 `COORDINATOR_SMOKE_FAIL: <错误代码>`。它不会打印任务原文、模型输出或认证令牌；不要发送本机绝对路径、密钥和原始 stderr。

**这是 Mac Studio 的本机 loopback 测试，不是手机端远程执行许可。** 尚未验收前，PR 保持草稿，不会开放局域网 Codex 访问。

## 合并此功能分支后的本机启动方法

以下指令仅用于 Mac Studio 本机，不要发送任何令牌或真实目录路径到公开 GitHub：

```sh
git clone https://github.com/foxmuldery/ai-desk.git
cd ai-desk
export AI_DESK_ENABLE_CODEX_READONLY=1
export AI_DESK_CODEX_READONLY_ROOT="$HOME/AI-Desk-Sandbox"
export AI_DESK_CODEX_TIMEOUT=180
sh scripts/run-local.sh
```

说明：
- 只有将功能 PR 合并后，`main` 才有真实 Codex 适配器；未合并前不能按此操作宣称已有可用功能。
- 本脚本默认绑定 `127.0.0.1:8765`，只允许 Mac 本机访问。
- 脚本会打印临时访问令牌；保留在本机，不要发送给其他人或写入仓库。
- 浏览器打开 `http://127.0.0.1:8765`，输入令牌。
- 任务适配器会出现“Codex 只读检查”；选择它，输入“只读阅读测试 README，概述仓库内容，不修改任何文件”。
- 成功时查看任务事件和简短总结，并检查仓库文件保持未修改。
- 运行环境/模型认证失败时不要重复提交大量任务，先记录脱敏错误类别。

## CLI 0.144.5 参数顺序修复（2026-10-24）

首次 Mac Studio smoke 结果：

- `PREFLIGHT_OK`：CLI、ChatGPT 登录及测试目录通过。
- `GIT_UNCHANGED`：测试目录未发现变化。
- `SMOKE_FAIL: CODEX_EXIT_2`：CLI 进程以状态 2 退出，尚未完成真实 Codex 回合。

已核对到 Codex CLI 的一个参数兼容问题：`--ask-for-approval never` 是**全局参数**，必须放在 `exec` 前面。错误组合 `codex exec --ask-for-approval never` 会被部分版本以退出码 2 拒绝。

- 错误示例：`codex exec --ask-for-approval never --sandbox read-only ...`
- 修正形式：`codex --ask-for-approval never exec --sandbox read-only ...`
- 参照官方仓库问题： https://github.com/openai/codex/issues/26602

已同步修正正式适配器和 smoke 脚本；预检现在会检查整个 `codex --ask-for-approval never exec --help` 的组合语法，而不仅仅检查各个参数是否在帮助中出现。

已克隆当前功能分支的 Mac Studio 用户不必重复 `git clone`。待 CI 全绿后：

```sh
cd "$HOME/AI-Desk-CLI-Test"
git pull --ff-only
sh scripts/check-codex.sh
sh scripts/smoke-codex-readonly.sh
```

如再次失败，只汇报输出的脱敏结果码（例如 `CODEX_ARGUMENT_PARSE_ERROR`、`CODEX_AUTH_ERROR`、`CODEX_EXIT_N`）。无需上传 stderr、Codex 认证内容或原始 JSONL。

## 实机验收

- [ ] `codex exec --help` 显示所需参数（0.144.5 本机确认）。
- [ ] 在同一 macOS 用户下 `codex login status` 显示 ChatGPT 已登录。
- [ ] 默认禁用 Codex，未启用时 API 返回 `CODEX_READONLY_DISABLED`。
- [ ] 本机启用时只出现 `codex-lab` 测试目录，不能指定其他项目路径。
- [ ] 实际进程执行完成，结果为 Codex 的真实汇报而非模拟内容。
- [ ] 验证目录中 `README.md`、`.git` 未被改写；检查 `git status`。
- [ ] 非零退出、`turn.failed`、空结果、超时都必须标记失败。
- [ ] 禁止对手机或 LAN 开放真实 Codex 适配器，直到远程授权与连接完成独立安全验收。
- [ ] 用真机记录实际 Codex CLI 兼容性和测试证据，更新 `docs/DEV_STATUS.md`。

## 后续：手机到 Mac

在本机只读闭环成功后，独立实现 S22 Ultra + Typeless 的认证、HTTPS、设备绑定、按操作分级审批。上线前必须实测浏览器通知和锁屏限制；不要因真实 CLI 可用就贸然放开 LAN 执行。
