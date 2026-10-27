# 初始化

完成标准：用户逐项决定过找到的诱因，当前 Agent 的全局指令里有最新的 `lean-audit` 块。

## 步骤

1. 运行 `python3 scripts/scan_env.py`。当前项目有自己的指令文件时加 `--project <项目路径>`。脚本列出找到的指令、配置、记忆和技能文件，以及命中诱因模式的行。
2. 逐条判断命中项，对照 [诱因](inducers.md) 归类。只保留确实会推动多做的条目：引原文，说明它诱导什么，给出删除或改写后的原文。然后把当前 Agent 的全局指令通读一遍，补上脚本没命中的同类句子。
3. 审查技能。列出会自动触发、且正文要求写测试或反馈循环、把调研和计划写进仓库、建术语表或决策记录、做多轮核对的技能，各给三个选项：关闭自动触发、卸载、保留。关闭方式：
   - Codex：技能的 `agents/openai.yaml` 写 `policy.allow_implicit_invocation: false`。
   - Claude Code：技能 `SKILL.md` 的 frontmatter 写 `disable-model-invocation: true`。
   - 改动第三方技能会形成本地改动，更新技能时需要重新应用，选项里写明这一点。
4. 把第 2、3 步整理成一份清单交给用户，由用户逐项决定。用户同意的项再动手。
5. 把 [规则](rules.md) 末尾的全局指令块写入下表对应的文件。已有 `lean-audit` 块时整块替换。旧指令里与它冲突的句子列给用户，一起决定删改。
6. 汇报改了哪些文件，每处一句。

## 各 Agent 的文件位置

| Agent | 全局指令 | 配置与记忆 | 技能 |
| --- | --- | --- | --- |
| Codex | `~/.codex/AGENTS.md` | `~/.codex/config.toml`、`~/.codex/memories/` | `~/.codex/skills/` |
| Claude Code | `~/.claude/CLAUDE.md` | `~/.claude/settings.json` | `~/.claude/skills/`、`~/.claude/agents/` |
| Gemini CLI | `~/.gemini/GEMINI.md` | `~/.gemini/settings.json` | — |
| 项目级 | `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`.cursor/rules/`、`.github/copilot-instructions.md` | — | `.claude/skills/`、`.agents/skills/` |

表里没有的 Agent，按它的文档找到用户级指令文件。Cursor 等只在界面里保存用户规则的应用，请用户把规则块粘贴进去。
