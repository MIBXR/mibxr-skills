# MIBXR Skills

把网页设计参考、影像与操作台参考、桌宠制作与交付的工作方法，整理成换一台电脑也能继续使用的 Agent 技能。

## 网页设计参考 Skill（web-atlas）

`$web-atlas` 把 [Web Atlas](https://github.com/MIBXR/web-atlas) 接入真实网站任务：先读现场、写简报，只补问会改变决定的问题，复述理解后检索收敛，再给出 2–3 个有差异的对照方案，拆解用户反应后定稿、取材、实现并验证。用户说不清想要什么时，也从真实内容和使用场景逐步找出方向，无需先知道 ID。

本仓库只保存工作流、检索脚本与上游配置。案例、巧思和素材数据、完整前端、交互样例、视觉预览和提示词由 `MIBXR/web-atlas` 维护；网站与 Agent 读取同一份资料，自动取得完整材料。

获取的案例包同时保留网页右侧说明的实际渲染内容、完整原始字段与文档，让 Agent 能核对网页说明与结构化资料。

[阅读技能正文](skills/web-atlas/SKILL.md)。Python 标准库脚本通过 `--session` 固定上游默认分支的 Git SHA，支持 `refresh`、指定 `--ref` 和离线 `--local-root`，状态保存在用户工作目录。案例、巧思与素材分别检索、分页和完整取材，导出保留仓库路径、版本与未下载媒体清单；参数及示例见 [CLI 参考](skills/web-atlas/references/cli.md)。

```text
请使用 $skill-installer，从 MIBXR/mibxr-skills 的 main 分支安装
skills/web-atlas。
如果已经安装同名技能，先保留本地修改，再更新。
```

```text
$web-atlas 我想给我的独立工作室做个官网，但说不清想要什么样子。
$web-atlas 这个 B2B 分析工具的落地页看起来很普通，帮我找方向并实现。
$web-atlas 参考 apple-product 的产品叙事和空间节奏，为我的真实产品实现落地页。
$web-atlas 我的作品集页面"太冷了，也没记忆点"，帮我改。
$web-atlas 为我的产品页挑选首屏聚焦与加载反馈的巧思，跨案例组合并实现。
```

## 影像与操作台参考 Skill（motion-atlas）

`$motion-atlas` 把 [Motion Atlas](https://github.com/MIBXR/motion-atlas) 接入时间线作品任务：先读现场、写简报，只补问会改变决定的问题，复述理解后检索收敛，再用关键帧条与短片段对照 2–3 个有差异的方向，拆解用户反应后定稿、取材、实现、验证并逐帧出片。用于影像视频和按时间线播放、带自动驾驶时间轴的交互操作台与展示台。

本仓库只保存工作流、检索脚本与上游配置。案例、巧思、节拍表、Prompt 与可逐帧渲染的 Demo 由 `MIBXR/motion-atlas` 维护；完整取材保留条目、Prompt、入口与文件清单。

[阅读技能正文](skills/motion-atlas/SKILL.md)。Python 标准库脚本通过 `--session` 固定上游默认分支的 Git SHA，支持 `refresh`、指定 `--ref` 和离线 `--local-root`，状态保存在用户工作目录。检索可按案例／巧思、载体和类型过滤并完整分页，导出保留仓库路径、版本与未下载文件清单；参数及示例见 [CLI 参考](skills/motion-atlas/references/cli.md)。

```text
请使用 $skill-installer，从 MIBXR/mibxr-skills 的 main 分支安装
skills/motion-atlas。
如果已经安装同名技能，先保留本地修改，再更新。
```

```text
$motion-atlas 我需要一支 30 秒的产品发布片头，放在发布会大屏上，不知道该做成什么风格。
$motion-atlas 把我这趟旅行的照片做成一支竖屏短片，节奏像游戏过场。
$motion-atlas 参考 archive-os，为我的展会做一个固定画幅、可以自动播放也能操作的档案展示台。
$motion-atlas 这段片头"太拖了，不够燃"，帮我改。
```

## 桌宠制作与交付 Skill

一个技能覆盖桌宠及其展示网站，按任务读取需要的经验。

| 要做什么 | 技能中保留的经验 |
| --- | --- |
| 设计与制作桌宠 | 主动联网研究角色、逐动作建议与确认、关键设计图确认、动作分镜、实际提示词和高清原稿。 |
| 修复已有动作 | 躯干对齐、比例与配色、道具稳定、循环接缝、最终图集与真实播放。 |
| 保存和发布作品 | 从制作开始使用 Git，组织来源、参考、素材和解包成品；独立版本提交、标签、逐动作预览与 Release。 |
| 制作宠物展示网站 | 寻找角色相关素材，由用户决定排版；角色介绍、动作剧场、安装、高清动画、透明边缘与交互。 |

[阅读技能正文](skills/desktop-pet-workflow/SKILL.md)。正文说明主流程，`references/` 保存按需阅读的经验，`agents/openai.yaml` 提供显示名称和调用示例；无需安装本仓库的运行依赖。

通用网站技能已合并：宠物网站的设计和注意事项现在属于这个技能，宠物与网站的文件和更新仍相对独立。

## 换电脑使用

这是公开仓库，可以直接安装。向 Codex 发送：

```text
请使用 $skill-installer，从 MIBXR/mibxr-skills 的 v1.4.0 标签安装
skills/desktop-pet-workflow。
如果已经安装同名技能，先保留本地修改，再更新。
```

要获取后续最新内容，可把版本改为 `main`。安装位置由当前环境决定；安装完成后按安装器提示使用。

## 可以这样调用

```text
$desktop-pet-workflow 根据这些参考制作桌宠，先联网研究角色，与我确认每个动作，再给关键设计图供确认。
$desktop-pet-workflow 修复挥手时身体抖动，保留其他动作，并给出逐动作预览。
$desktop-pet-workflow 把这些版本整理成作品仓库，素材解包保存，Release 放便携包。

$desktop-pet-workflow 为我的桌宠寻找相关网站素材，先给排版建议让我选择，再制作并保存到 Git。
$desktop-pet-workflow 宠物网站的动画模糊、边缘有杂色，检查已有高清原稿并修复。
$desktop-pet-workflow 保存宠物网站的完整源码和素材，这次只整理，不部署。
```

## 经验如何使用

这些方法来自实际的桌宠制作、动画返工、网站制作与仓库整理。角色特征、配色和文案以当前作品为准；技能保留处理问题的方法，不携带旧项目的路径、账号、临时链接或素材。

制作过程需要的图像工具、浏览器和发布能力，使用目标环境已有的工具与授权。作品仓库以介绍作品、保存创作过程和成果为主；临时加工工具与检查记录留在任务工作区。
