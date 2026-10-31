# MIBXR Skills

把与 AI 协作中反复用到的工作方法整理成 Agent 技能，换一台电脑或换一个 Agent 也能继续使用。

| 技能 | 版本 | 用途 |
| --- | --- | --- |
| [web-atlas](#网页设计参考web-atlas) | `1.0.0` | 网站与网页应用的设计：剖析需求，从 Web Atlas 选择并组合案例、巧思和素材，取得源码后实现页面。 |
| [motion-atlas](#影像与操作台参考motion-atlas) | `1.0.0` | 按时间线播放的作品：片头、宣传片、数据短片和交互操作台，从 Motion Atlas 取材，实现后逐帧出片。 |
| [desktop-pet-workflow](#桌宠制作与交付desktop-pet-workflow) | `1.0.0` | 桌宠的设计、制作、动作修复、展示网站与 Git 交付。 |
| [lean-audit](#精简审查lean-audit) | `1.0.0` | 找出 Agent 配置里诱发过度设计的写法，开发完成后找出改动里超出计划的部分。 |

## 安装

在 Codex 中发送（把技能名换成要安装的那个）：

```text
请使用 $skill-installer，从 MIBXR/mibxr-skills 的 main 分支安装
skills/web-atlas。
如果已经安装同名技能，先保留本地修改，再更新。
```

每个技能单独发布版本，标签为 `<技能名>@<版本>`，例如 `web-atlas@1.0.0`。安装固定版本时，把上面的“main 分支”换成对应标签。

在 Claude Code 等其他 Agent 中，把 `skills/<技能名>/` 整个目录复制到该 Agent 的技能目录，例如 `~/.claude/skills/<技能名>/`。

每个技能的 `SKILL.md` 说明主流程，`references/` 保存按需阅读的细节，`agents/openai.yaml` 提供 Codex 中的显示名称和默认提示词。带脚本的技能只依赖 Python 3 标准库。

安装后用 `$技能名` 加上要做的事调用，下面各节附有示例。

## 网页设计参考（web-atlas）

`$web-atlas` 把 [Web Atlas](https://github.com/MIBXR/web-atlas) 接入真实网站任务：先读现场、写简报，只补问会改变决定的问题，复述理解后检索收敛，再给出 2–3 个有差异的对照方案，拆解用户反应后定稿、取材、实现。用户说不清想要什么时，也从真实内容和使用场景逐步找出方向，无需先知道 ID。

本仓库只保存工作流、检索脚本与上游配置。案例、巧思和素材数据、完整前端、交互样例、视觉预览和提示词由 `MIBXR/web-atlas` 维护；网站与 Agent 读取同一份资料。取得的案例包含网页右侧说明的渲染内容、完整原始字段与文档。

[阅读技能正文](skills/web-atlas/SKILL.md)。检索脚本通过 `--session` 固定上游默认分支的 Git SHA，支持 `refresh`、指定 `--ref` 和离线 `--local-root`，状态保存在用户工作目录。案例、巧思与素材分别检索、分页和完整取材，导出保留仓库路径、版本与未下载媒体清单；参数及示例见 [CLI 参考](skills/web-atlas/references/cli.md)。

```text
$web-atlas 我想给我的独立工作室做个官网，但说不清想要什么样子。
$web-atlas 这个 B2B 分析工具的落地页看起来很普通，帮我找方向并实现。
$web-atlas 参考 apple-product 的产品叙事和空间节奏，为我的真实产品实现落地页。
$web-atlas 我的作品集页面"太冷了，也没记忆点"，帮我改。
$web-atlas 为我的产品页挑选首屏聚焦与加载反馈的巧思，跨案例组合并实现。
```

## 影像与操作台参考（motion-atlas）

`$motion-atlas` 把 [Motion Atlas](https://github.com/MIBXR/motion-atlas) 接入时间线作品任务：先读现场、写简报，只补问会改变决定的问题，复述理解后检索收敛，再用关键帧条与短片段对照 2–3 个有差异的方向，拆解用户反应后定稿、取材、实现并逐帧出片。用于影像视频和按时间线播放、带自动驾驶时间轴的交互操作台与展示台。

本仓库只保存工作流、检索脚本与上游配置。案例、巧思、素材、节拍表、Prompt 与可逐帧渲染的 Demo 由 `MIBXR/motion-atlas` 维护；完整取材保留条目、Prompt、入口与文件清单。

[阅读技能正文](skills/motion-atlas/SKILL.md)。检索脚本的会话与版本用法和 web-atlas 相同，可按案例／巧思／素材、载体和类型过滤并完整分页；参数及示例见 [CLI 参考](skills/motion-atlas/references/cli.md)。

```text
$motion-atlas 我需要一支 30 秒的产品发布片头，放在发布会大屏上，不知道该做成什么风格。
$motion-atlas 把我这趟旅行的照片做成一支竖屏短片，节奏像游戏过场。
$motion-atlas 参考 archive-os，为我的展会做一个固定画幅、可以自动播放也能操作的档案展示台。
$motion-atlas 这段片头"太拖了，不够燃"，帮我改。
```

## 桌宠制作与交付（desktop-pet-workflow）

`$desktop-pet-workflow` 覆盖桌宠及其展示网站，按任务读取需要的经验。

| 要做什么 | 技能中保留的经验 |
| --- | --- |
| 设计与制作桌宠 | 主动联网研究角色、逐动作建议与确认、关键设计图确认、动作分镜、实际提示词和高清原稿。 |
| 修复已有动作 | 躯干对齐、比例与配色、道具稳定、循环接缝、最终图集与真实播放。 |
| 保存和发布作品 | 从制作开始使用 Git，组织来源、参考、素材和解包成品；独立版本提交、标签、逐动作预览与 Release。 |
| 制作宠物展示网站 | 寻找角色相关素材，由用户决定排版；角色介绍、动作剧场、安装、高清动画、透明边缘与交互。 |

[阅读技能正文](skills/desktop-pet-workflow/SKILL.md)。

```text
$desktop-pet-workflow 根据这些参考制作桌宠，先联网研究角色，与我确认每个动作，再给关键设计图供确认。
$desktop-pet-workflow 修复挥手时身体抖动，保留其他动作，并给出逐动作预览。
$desktop-pet-workflow 把这些版本整理成作品仓库，素材解包保存，Release 放便携包。
$desktop-pet-workflow 为我的桌宠寻找相关网站素材，先给排版建议让我选择，再制作并保存到 Git。
$desktop-pet-workflow 宠物网站的动画模糊、边缘有杂色，检查已有高清原稿并修复。
```

## 精简审查（lean-audit）

`$lean-audit` 处理 Agent 的过度设计与过度防御：顺手加的测试和哈希、走不到的兜底分支、文档里的免责句和讨论过程、为一个案例搭的抽象。只在点名时运行，有两种用法：

| 用法 | 做什么 |
| --- | --- |
| 初始化 | 扫描当前电脑上 Codex、Claude Code、Gemini CLI 和项目里的指令、配置、记忆与技能，列出诱发多做的写法和会自动触发的相关技能，由你逐项决定修改，再把精简原则写入全局指令。 |
| 完成审查 | 开发完成后扫描这次改动，列出计划外的文件、测试与哈希代码、兜底分支、免责句和重复说明，由你决定删除。 |

[阅读技能正文](skills/lean-audit/SKILL.md)。判断标准集中在 [规则](skills/lean-audit/references/rules.md)；`scripts/scan_env.py` 与 `scripts/scan_diff.py` 只读，输出 JSON 供 Agent 判断。

```text
$lean-audit 初始化，检查我现在的 Agent 配置。
$lean-audit 开发完了，按 issue #12 检查这个分支有没有多做。
$lean-audit 检查 main..HEAD 的改动，docs/vendor/ 是原样复制进来的。
```

## 经验从哪里来

这些技能来自实际的网站与影像制作、桌宠制作与返工、仓库整理，以及与 Codex、Claude Code 等 Agent 的协作。技能保存处理问题的方法；具体项目的品牌、配色、文案和角色特征以当前作品为准，旧项目的路径、账号、临时链接和素材不随技能携带。

任务需要的图像工具、浏览器和发布能力，使用所在环境已有的工具与授权。过程中的临时工具、检查记录和截图留在任务工作区，作品仓库只保存交付物。
