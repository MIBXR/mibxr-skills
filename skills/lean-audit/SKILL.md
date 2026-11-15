---
name: lean-audit
description: 审查 Agent 的过度设计和过度防御。初始化审查环境配置，开发前核对改动范围，交付前审查实际变化是否超出需求。仅在用户点名调用时使用。
disable-model-invocation: true
---

# Lean Audit 精简审查

Agent 容易把个人项目当成需要长期维护的团队产品：顺手加测试和校验，为走不到的分支写兜底，在文档里写免责和讨论过程，为单个案例建立抽象。

什么算多余，以 [判断规则](references/rules.md) 为唯一标准。

## 选择模式

| 用户的说法 | 模式 |
| --- | --- |
| 第一次使用、“初始化”“检查我的配置”、换了 Agent 或电脑 | 初始化，按 [初始化](references/setup.md) 执行 |
| “动手前定范围”“核对改动计划” | 按 [确定改动范围](references/review.md#确定改动范围) 执行 |
| “开发完了”“检查这次改动”“有没有多做” | 按 [完成审查](references/review.md#审查步骤) 执行 |

用本技能协助实施任务时，动手前确定改动范围，交付前完成审查。结合上下文选择步骤，仍有歧义时再询问。

## 脚本

两个脚本只依赖 Python 3 标准库，以只读方式扫描并输出 JSON。你逐条判断结果后，交给用户决定。

- `scripts/scan_env.py`：找出当前电脑上各 Agent 的全局指令、配置、记忆与技能，标出诱因句和会自动触发的技能。
- `scripts/scan_diff.py`：扫描一段改动。`flags` 列出命中的路径或代码规则，`review` 列出需要逐句判断的文档内容。

参数见各脚本的 `--help`。Windows 上用 `python` 代替 `python3`。
