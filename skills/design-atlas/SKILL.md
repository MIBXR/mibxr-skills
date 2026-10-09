---
name: design-atlas
description: 从 Design Atlas 选择前端案例及视觉、微动效、页面动效、声音与内容组织巧思，自动取得源码、提示词和来源上下文来实现网站。用于选择风格、借鉴独立机制、跨案例组合或按指定案例构建页面；网站案例库维护使用其仓库说明。
---

# Design Atlas 前端设计参考

从完整案例选择视觉方向，从设计巧思选择可独立借用的机制，再结合当前产品实现网站。一个页面可以组合多个案例的巧思。案例、巧思及其来源由 [MIBXR/design-atlas](https://github.com/MIBXR/design-atlas) 维护；本技能保存工作流与轻量检索工具，网站保留人类预览。用户无需预先知道 ID，也无需手动复制源码或 Prompt。

## 建立本次取材会话

使用 `scripts/atlas.py`（Python 3，仅标准库）。新会话先读取上游仓库的默认分支及最新完整 Git SHA；案例与巧思共享这次会话的 SHA，后续探索、筛选、取材和导出保持一致。

远程取材时，在用户当前项目的 `work/` 中选一个会话 JSON 路径，每次调用都传给 `--session`。脚本不向技能安装目录写状态。离线的 `--local-root CHECKOUT` 读取当前工作树，不能与 `--session` 或 `--ref` 同用；复现时保存该工作树及输出的 `contentVersion`，后续调用会读取新落盘的内容。下例中的 `ATLAS_SCRIPT` 是技能脚本的实际路径，`SESSION_FILE` 是本次用户工作目录中的 JSON 路径；命令输出 UTF-8 JSON，所有全局参数放在子命令前。

```bash
python ATLAS_SCRIPT --session SESSION_FILE search "" --limit 100 --offset 0
python ATLAS_SCRIPT --session SESSION_FILE search "产品 深色" --limit 5
python ATLAS_SCRIPT --session SESSION_FILE search "" --category "产品" --limit 100
python ATLAS_SCRIPT --session SESSION_FILE show linear-workflow
python ATLAS_SCRIPT --session SESSION_FILE show linear-workflow --source
python ATLAS_SCRIPT --session SESSION_FILE export linear-workflow --out NEW_DIRECTORY
python ATLAS_SCRIPT --session SESSION_FILE pattern-search "" --limit 100 --offset 0
python ATLAS_SCRIPT --session SESSION_FILE pattern-search "悬停 聚焦" --limit 5
python ATLAS_SCRIPT --session SESSION_FILE pattern-search "" --type visual --limit 100
python ATLAS_SCRIPT --session SESSION_FILE pattern-search "按钮" --type micro-motion
python ATLAS_SCRIPT --session SESSION_FILE pattern-search "切换" --type page-motion
python ATLAS_SCRIPT --session SESSION_FILE pattern-search "" --type sound
python ATLAS_SCRIPT --session SESSION_FILE pattern-search "" --category "交互反馈" --case chatgpt-platform
python ATLAS_SCRIPT --session SESSION_FILE pattern-show PATTERN_ID --source
python ATLAS_SCRIPT --session SESSION_FILE pattern-export PATTERN_ID --out NEW_DIRECTORY
```

按当前任务选择 `search`（完整案例）或 `pattern-search`（独立巧思），空查询读取目录。若 `hasMore` 为 `true`，保持同一会话、查询与过滤，把 `--offset` 增加本次 `limit` 继续读取，直到 `hasMore` 为 `false`；单页上限为 100，两个目录的总量均不限。查询支持中文和英文关键词，输出命中字段、适用场景与谨慎使用项；分数用于排序，适合程度结合真实需求判断。巧思可按单个 `--type` 体验类型、`--category` 功能分类、`--case` 来源案例共同过滤；`experienceTypes` 可含多个类型，命中其中一个即符合类型过滤。

体验类型由上游逐项标注：`visual` 是排版、色彩、装饰和形状等静态视觉机制；`micro-motion` 是按钮、卡片等局部反馈或辅助动效；`page-motion` 是首屏、滚动叙事、页面过渡等主体动效；`sound` 是背景音乐和操作音；`structure` 是内容组织、导航和信息关系。按当前产品的问题筛选，不要求每个案例具备全部类型，也不为凑类型拆分机制。声音适用于游戏、品牌叙事等确有听觉需求的场景，结合声音巧思包的来源观察与核验边界选择。

需要取得后来新增的案例或巧思时，显式刷新会话后重新检索：

```bash
python ATLAS_SCRIPT --session SESSION_FILE refresh
```

刷新先验证案例索引、巧思索引的仓库、schema、清单与摘要，再原子替换会话；失败保留原会话。无需会话的 `info` 查看当前最新版本及两个目录的数量。默认解析失败会明确报错；已有会话、`--ref FULL_COMMIT` 复现模式及 `--local-root CHECKOUT` 离线模式各自可用。后两种模式的全局参数也放在子命令前。旧版本仍支持案例命令；缺少巧思目录或体验类型时工具提示刷新或选择新版。无类型标注的旧巧思仍可读取、导出和不带 `--type` 检索，检索输出中的空 `experienceTypes` 表示未分类。`upstream.lock.json` 保存上游配置和已验证基线，基线不限制默认发现新增内容。

## 探索并迭代筛选

用户只问库里有哪些时，浏览相应完整目录，介绍分类与适用方向；这一步无需当前项目需求。仅探索或比较的任务交付目录与候选说明。需要选择风格或构建网站时，读取当前项目与用户内容，明确页面用途、主要使用者、内容密度、关键操作、技术栈及已有设计约束，用用途、布局、交互与视觉要求检索；候选不足时换关键词或扩大分类。

根据真实需求比较少量候选，说明能借用的机制与适配代价，围绕内容、功能和反馈收敛到足以解释当前产品的方向。需求变化时保留已知约束，重新筛选。用户已经指定案例或巧思时直接读取；已授权构建且需求、选择依据明确时，自主继续完整取材与实现。

组合时先确定主视觉与信息层级由哪个案例或 `composition.role=foundation` 的巧思承担，再为 `support` 和 `accent` 指定组件或交互职责。以目标页面的问题选择跨案例机制，参考 `pairsWellWith`、`conflicts` 与 `composition.notes`，逐项检查触发事件、动态强度、注意力竞争和布局是否冲突；这些关系是设计建议，仍需结合当前内容验证。明确触发与效果、参数、键盘行为及减少动态后的状态，避免把多个案例的全屏加载、背景运动和滚动接管同时堆在一个流程。

候选摘要只用于选择。实现前对最终案例执行 `show --source`，对最终巧思执行 `pattern-show PATTERN_ID --source`。巧思包包含完整机制、Prompt、参数、来源观察与证据等级，以及核验后的 `sourceCaseBundles`；`source` 自动读取 `sourceFiles` 中的实际源码。形成包含案例／巧思 ID、上游 commit、职责与适配方式的短设计依据。`sources[].evidence` 区分实站观察 `observed`、教学改编 `adapted` 与推导 `inferred`；通过来源案例理解机制在完整页面中的效果，按原有证据等级表述。

同时读取 `webNotes.content`：它保留同一版本 `atlas.js` 实际渲染的详情右侧说明 HTML，覆盖设计机制、交互、约束、Tokens、Prompt 和来源证据。把网页说明与完整字段、文档对照后取材，保留采集／理论核验日期、近似和未验证标记。发生差异时先检查是否混用了网页与数据版本，再取得同一 SHA 的材料；仍有差异时列出具体字段与说明，按本次任务修复或报告。

## 取得完整材料并实现

需要可运行参考时执行 `export` 或 `pattern-export`，保留仓库相对目录并核验全部文件。目标目录必须尚不存在。巧思导出自动取得相关案例的完整 demo、素材和上下文，`atlas-export.json` 保留巧思包、`sourceFiles`、来源案例包、文件摘要与上游版本；以原子机制的职责取材，完整 demo 用于理解页面关系。两种导出均支持 `--code-only` 仅下载源码与上下文，并列明未下载素材及预览。完整预览媒体按清单补齐，用静态 HTTP 服务器服务导出根目录，打开案例输出的 `entrypoint` 或巧思输出的 `entrypoints[].path`。

从案例提取信息层级、布局节奏、色彩、字体、组件状态、交互和响应式行为，应用到当前真实内容与功能。保留项目结构与用户确认的约束，按当前任务实现所需模块。案例中的品牌、占位内容、外部素材和模拟行为各有来源，按当前产品替换或核实。

区分原始提示词、设计解读、实际源码和后补说明，避免把解读当作真实生成记录。用户要求复现时尊重指定视觉；用户要求借鉴时说明保留哪些原则、如何适配当前场景。

## 验证并交付

按当前项目方式构建和运行，检查真实内容下的主要页面、窄屏布局、关键交互、键盘操作、减少动态、可读性及资源加载。动效实测起始、过程、完成与回程；声音实测触发、静音、重复播放、手机入口和后台行为，记录未验证项及本地适配边界。对照选中案例检查设计依据是否落实；同一任务的材料来自同一会话 SHA，刷新后需要重新确认候选与资料。

交付时列明引用的案例／巧思 ID、上游版本、组合职责、完成的适配和实际验证结果。[Agent 协议说明](https://github.com/MIBXR/design-atlas/blob/master/AGENT.md) 与 `agent/catalog.json`、`agent/cases/<id>.json`、`agent/patterns.json`、`agent/patterns/<id>.json` 提供直接读取入口；当前项目的运行结果决定交付是否完成。
