# S22 Ultra ↔ Mac Studio：AI Desk 安全手机联调（仅 dry-run）

**阶段：实验性手机接入。绝不执行远程 Codex、shell 或对项目文件的写操作。**

截至本文件版本，Mac Studio 本地 AI Desk → 真正的 Codex 只读闭环已获用户本机 `COORDINATOR_SMOKE_OK` 证据。手机接入是**另一项独立验收**，不能因为本机成功就默认安全。

## 网络方案与限制

使用 **Tailscale Serve（不是 Funnel）**，在同一个 tailnet 内把 Mac Studio 的 `127.0.0.1:8766` 局域网不可直接访问的 HTTP 服务映射为仅 tailnet 可访问的可信 HTTPS URL：

```text
S22 Ultra Chrome + Typeless
    │ HTTPS（tailnet 私有名称，Tailscale 自动证书）
    ▼
Mac Studio 的 Tailscale Serve
    │ HTTP → 127.0.0.1:8766（仅同机代理）
    ▼
AI Desk phone-dry-run Profile
    │ 强随机令牌 + 仅 dry-run 任务 + SQLite
    ▼
模拟任务结果 → 手机网页
```

- 不需要购置电话硬件，不刷 Linksys MX5300 固件，不开公网端口。
- Mac Studio 和 S22 Ultra 需安装并登录**同一个 Tailscale tailnet**；两台设备需要获得 tailnet 中相互访问的 ACL 授权。Tailscale 安装与登录需要用户自己在两台设备上完成；不要把账号密码或认证密钥发给其他人。
- Tailscale Serve 与 Tailscale Funnel 不同：**Funnel 可以公开到互联网，此项目严禁使用 Funnel。**
- Serve 的自动 HTTPS 需要 tailnet 中启用 MagicDNS / HTTPS 证书；首次启用可能出现管理员授权页。不要绕过证书警告。
- HTTPS/Tailscale 解决传输和网络成员访问，**不是任务执行权限**。后端还要求独立强令牌和强制的 `phone-dry-run` Profile，并禁止真实 Codex；即使恶意客户端伪造 `X-Forwarded-For` 也无法开启它。
- Tailscale Serve 的 HTTPS 在 Mac 上终止，之后转发至本机 `127.0.0.1`。不要复用已经启用真实 Codex 的 Coordinator 实例，也不要把这个 loopback 服务改成非 loopback 绑定。

## 步骤 0：只读前置检查

在 Mac Studio 的终端执行：

```sh
command -v tailscale || true
tailscale version
tailscale status
tailscale serve status
tailscale funnel status
```

**如果终端提示 `tailscale: command not found`：** 可能是未安装，也可能是 macOS 应用内置 CLI 未加入 PATH。

- Tailscale Standalone 客户端支持通过设置中的 CLI integration 安装命令。
- Mac App Store 版本可尝试：
  `TAILSCALE_BE_CLI=1 /Applications/Tailscale.app/Contents/MacOS/Tailscale version`
- 不必马上安装或更改任何网络设置；先确认两台设备上的 Tailscale 是否可登录、能互相看到。
- 如果 `tailscale serve status` 已有其它服务，**不要继续执行会覆盖配置的命令**；记录“已有 Serve”并先评估如何选用独立端口，避免破坏已有站点。
- 不要在聊天中粘贴未脱敏的 `tailscale status` 完整输出，因为可能包含内部设备名、tailnet 名称和 IP。

官方参考：
- [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)
- [Serve CLI](https://tailscale.com/docs/reference/tailscale-cli/serve)
- [Tailscale Android 安装](https://tailscale.com/docs/install/android)
- [macOS Tailscale CLI](https://tailscale.com/docs/reference/tailscale-cli)

## 步骤 1：在 Mac Studio 启动明确禁止真实 Codex 的手机实验服务

**与先前的 Mac Studio `AI-Desk-CLI-Test` 实验目录分开**。在新的空目录克隆手机联调分支：

```sh
git clone --single-branch --branch feat/phone-dry-run-tailnet \
  https://github.com/foxmuldery/ai-desk.git "$HOME/AI-Desk-Phone-Test"
cd "$HOME/AI-Desk-Phone-Test"
sh scripts/run-phone-dryrun.sh
```

如果已经存在 `AI-Desk-Phone-Test`，不要覆盖；只在该目录确认分支后 `git pull --ff-only`。

脚本会：
- 强制 `AI_DESK_EXECUTION_PROFILE=phone-dry-run`；
- 强制 `AI_DESK_ENABLE_CODEX_READONLY=0`（即使此前 Shell 环境设置为 1）；
- 绑定 `127.0.0.1:8766` 而不是 `0.0.0.0`；
- 创建随机临时用户令牌和独立 SQLite 数据库；
- **不调用 Codex，不运行任意 shell**（启动器只启动 AI Desk 进程）；
- 在本机终端显示令牌，仅供测试时输入手机网页，不要截图/发送到 GitHub。

请保持这个终端打开。关停服务使用 `Ctrl+C`。

## 步骤 2：在 Mac Studio 第二个终端确认 Tailscale Serve 路由

确认 Serve 端口没有已存在的配置、Tailscale 已正常登录且允许此设备进行 Serve 后，在**第二个终端**运行：

```sh
tailscale serve --https=8443 http://127.0.0.1:8766
```

不要加 `--bg`，这样测试时路由只在前台存在；不要使用 `tailscale funnel`。CLI 会显示 tailnet 内 HTTPS 地址，通常形如 `https://<设备>. <tailnet>.ts.net:8443`（实际以你的终端打印为准，域名中**没有空格**）。

如果 Tailscale 要求在浏览器上确认启用 HTTPS，按指引由本人授权。若与已有 Serve 配置冲突，停止操作，不使用 `tailscale serve reset`（这可能清除其他服务）。

在浏览器打开输出的 HTTPS 地址，并确认地址栏**没有证书警告**。不允许绕过浏览器证书检查。

## 步骤 3：S22 Ultra 登录 Tailscale 并打开 AI Desk

1. 安装并登录 Android 端 Tailscale，加入与 Mac Studio 相同的 tailnet；确认 VPN 已连接。
2. 在 S22 Ultra 的 Chrome 中输入第二个终端输出的 `https://...` 地址。
3. 页面打开后，从 Mac Studio **本机终端**取得仅用于此次测试的临时令牌，在手机访问令牌框中输入；不要把令牌贴到 URL、聊天、截图或 GitHub。
4. 检查服务状态为在线，适配器只出现 **Dry-run（仅模拟）**；如果出现真实 Codex 选项，**立即停止**。
5. 点任务输入框，切换 Typeless，以中文说出：`测试 AI Desk 的模拟任务派发，不允许执行任何真实操作。` 核对转写文本后点击提交。
6. 观察任务从已接收/排队至 **模拟完成**，打开任务事件；刷新页面后再次输入令牌，确认能恢复列表及刚刚的任务记录。
7. 断开手机 Wi-Fi 并恢复一次，观察连接失败提示、重连后的状态；在页面前台测试中文 TTS 是否播报。后台锁屏通知目前不作为通过条件。

## 步骤 4：测试结束及时关闭

- 在第二个终端对前台 `tailscale serve ...` 按 `Ctrl+C` 退出。
- 在第一个终端对 `sh scripts/run-phone-dryrun.sh` 按 `Ctrl+C` 结束。
- 执行 `tailscale serve status` 确认临时路由已停止。若仍显示相同的 8443 临时路由且确认由你本次创建，可用：
  `tailscale serve --https=8443 off`
- **绝对不要使用 `tailscale serve reset` 来清理这个测试**，除非你确认没有其它业务使用同一配置。

## 验收结果（只回传脱敏结果）

只需告诉开发线程以下项目是否成功，或者失败在哪一步：

| 检查项目 | 结果 |
|---|---|
| Mac Studio Tailscale 可运行并已连接 | PASS / FAIL |
| 安卓端同一 tailnet，可信 HTTPS 可打开 | PASS / FAIL |
| 只有 dry-run，实际 Codex 被后端禁止 | PASS / FAIL |
| Typeless 能在任务框内输入中文 | PASS / FAIL |
| 任务提交、模拟完成、事件查询、刷新恢复 | PASS / FAIL |
| 前台中文语音播报 | PASS / FAIL / 未支持 |
| 后台通知与锁屏 | 未测试（后续单独设计） |

**不要发送**：任何密码、Tailscale 密钥、内网 IP、完整设备 DNS 名称、访问令牌或未脱敏网络截图。

## 重要：安全划界

Mac Studio 的 Codex-only smoke 和 Coordinator→Codex smoke 虽然都已经成功，但本次 Tailscale Serve **只代理隔离的 phone-dry-run 服务**。未经独立安全审批，不得让手机或 tailnet 节点远程调用真实 Codex。
