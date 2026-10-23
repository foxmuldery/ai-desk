# 应用适配器框架

## 设计原则

AI Desk 的核心是调度与状态管理。每个应用通过独立适配器接入，适配器必须有明确的输入、权限、输出和验收规则。不能因为用户说“帮我操作某应用”就执行任意 shell 命令。

## 适配器接口草案

每个适配器提供：
- adapter_id 与版本。
- 描述和能力声明。
- 参数 schema 校验。
- 所需权限和允许目录。
- 超时与取消策略。
- 幂等性说明。
- 执行入口。
- 结构化结果。
- 验收函数。
- 单元/集成测试。

逻辑接口：

    validate(input, context) -> validation_result
    authorize(input, user_policy) -> authorization_result
    execute(input, execution_context) -> execution_handle
    collect(execution_handle) -> result
    verify(result, acceptance_policy) -> verification_result

## 首批适配器优先级

### 1. Dry-run / echo adapter
用于验证整个任务生命周期。只回显经过校验的任务摘要，不运行系统命令。

### 2. 文件检查 adapter
仅扫描配置好的允许目录，报告文件清单、大小、修改时间和哈希。默认只读。

### 3. Test runner adapter
运行管理员预先登记的测试命令与项目配置。调用预定义脚本 ID，不接受手机传来的任意 shell 文本。

### 4. Codex adapter
调用本机安装的 Codex CLI/SDK。必须在实现前核实实际版本、支持的执行接口和审批模式。

### 5. Git adapter
状态、diff、测试摘要等只读操作先行；commit、push、发布等写操作单独配置权限和确认门槛。

### 6. Browser adapter
优先采用应用官方 API 或经授权的浏览器自动化会话。登录凭据不从任务文本读取，也不将浏览器 cookie 写入日志。

### 7. Blender / 媒体处理 adapter
优先使用脚本、命令行或应用官方接口。渲染任务必须声明输入资产、输出目录、预计资源占用和验收规则。

## 结果结构示例

    {
      "status": "succeeded",
      "summary": "测试通过",
      "exit_code": 0,
      "checks": [
        {"name": "unit_tests", "status": "passed"}
      ],
      "artifacts": [
        {"kind": "report", "path_ref": "artifact_123"}
      ],
      "warnings": []
    }

示例仅为接口草案。真实成功状态必须由实际执行与验收证据决定。

## 禁止模式

- 直接把自然语言当作 shell 命令执行。
- 用无界权限执行任意应用操作。
- 把进程启动成功当作任务完成。
- 对非幂等操作自动无限重试。
- 让一个应用适配器持有不必要的所有电脑权限。
