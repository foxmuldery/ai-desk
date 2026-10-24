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

该步骤只在新建的测试目录内创建文件，`codex exec --help` 只打印帮助信息，不会启动推理任务。
检查帮助中是否包含 `--sandbox`、`--json`、`--output-last-message`、`--ignore-user-config`、`--ephemeral`。如果版本不支持某个参数，先反馈帮助信息，不要为了测试强行修改 Codex 配置或升级。

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
