---
name: design-atlas
description: 从 Design Atlas 探索前端设计案例，围绕真实需求迭代筛选，再取得完整源码、提示词和设计上下文来实现网站。用于尚未选定风格、比较设计方向或按指定案例构建页面；网站案例库维护使用其仓库说明。
---

# Design Atlas 前端设计参考

先探索案例，再结合当前产品收敛设计方向，最后自动取得完整材料并实现网站。完整案例由 [MIBXR/design-atlas](https://github.com/MIBXR/design-atlas) 维护；本技能保存工作流与轻量检索工具，人类预览网站继续保留。用户无需预先知道案例 ID，也无需手动复制源码或 Prompt。

## 建立本次取材会话

使用 `scripts/atlas.py`（Python 3，仅标准库）。新会话先读取上游仓库的默认分支及最新完整 Git SHA；后续探索、筛选、取材和导出都沿用这次会话的 SHA，在发现新增案例与避免版本混用之间保持一致。

每个任务在用户当前项目的 `work/` 中选一个会话 JSON 路径，始终把它传给 `--session`。脚本不向技能安装目录写状态。下例中的 `ATLAS_SCRIPT` 是技能脚本的实际路径，`SESSION_FILE` 是本次用户工作目录中的 JSON 路径；命令输出 UTF-8 JSON，所有全局参数放在子命令前。

```bash
python ATLAS_SCRIPT --session SESSION_FILE search "" --limit 100 --offset 0
python ATLAS_SCRIPT --session SESSION_FILE search "产品 深色" --limit 5
python ATLAS_SCRIPT --session SESSION_FILE search "" --category "产品" --limit 100
python ATLAS_SCRIPT --session SESSION_FILE show linear-workflow
python ATLAS_SCRIPT --session SESSION_FILE show linear-workflow --source
python ATLAS_SCRIPT --session SESSION_FILE export linear-workflow --out NEW_DIRECTORY
```

第一条命令开始读取完整目录。若 `hasMore` 为 `true`，保持同一会话与查询，把 `--offset` 增加本次 `limit` 继续读取，直到 `hasMore` 为 `false`；单页上限为 100，目录总量不受该上限限制。`search` 是关键词匹配，输出命中字段、适用场景和谨慎使用项，分数用于排序，适合程度仍需结合真实需求判断。

需要取得后来新增的案例时，显式刷新会话后重新检索：

```bash
python ATLAS_SCRIPT --session SESSION_FILE refresh
```

刷新先验证新索引的仓库、schema 和摘要，再原子替换会话；失败保留原会话。无需会话的 `info` 可以查看当前最新版本。默认解析失败会明确报错；已有会话、`--ref FULL_COMMIT` 复现模式及 `--local-root CHECKOUT` 离线模式各自可用。后两种模式的全局参数也放在子命令前。`upstream.lock.json` 保存上游配置和已验证基线，基线不限制默认发现新增案例。

## 探索并迭代筛选

用户只问库里有哪些时，先浏览完整目录、介绍分类与适用方向；这一步无需当前项目需求。仅探索或比较的任务交付目录与候选说明，按用户本次范围完成。需要选择风格或构建网站时，再读取当前项目与用户内容，明确页面用途、主要使用者、内容密度、关键操作、技术栈及已有设计约束，用用途、布局、交互与视觉要求检索；候选不足时换关键词或扩大分类。

根据真实需求比较少量候选，说明各自能借用的设计机制与适配代价。继续围绕内容、功能和用户反馈收敛候选，直到选定的方向足以解释当前产品；需求变化时保留已知约束，重新检索与筛选。使用多例时明确一个主参考负责整体视觉与层级，辅助案例只承担指定组件或交互。用户已经指定案例时，直接进入该案例；已授权构建且需求、选择依据明确时，自主继续完整取材与实现。

候选摘要只用于选择。开始实现前对最终案例执行 `show --source`，自动读取完整原始 `entry`、`documents` 和源码，形成包含案例 ID、上游 commit、采用原则与适配方式的短设计依据。资料路径与可用性以返回清单为准；缺失资料标明缺失。

同时读取 `webNotes.content`：它保留同一版本 `atlas.js` 实际渲染的详情右侧说明 HTML，覆盖设计机制、交互、约束、Tokens、Prompt 和来源证据。把网页说明与完整字段、文档对照后取材，保留采集／理论核验日期、近似和未验证标记。发生差异时先检查是否混用了网页与数据版本，再取得同一 SHA 的材料；仍有差异时列出具体字段与说明，按本次任务修复或报告。

## 取得完整材料并实现

需要可运行参考时执行 `export`，保留仓库相对目录并核验全部文件。目标目录必须尚不存在；`--code-only` 仅下载源码和上下文，`atlas-export.json` 保存完整案例包，并明确列出未下载素材与预览。完整预览所需媒体按清单补齐，用当前环境的静态 HTTP 服务器服务导出根目录，再打开输出中的 `entrypoint`。

从案例提取信息层级、布局节奏、色彩、字体、组件状态、交互和响应式行为，应用到当前真实内容与功能。保留项目结构与用户确认的约束，按当前任务实现所需模块。案例中的品牌、占位内容、外部素材和模拟行为各有来源，按当前产品替换或核实。

区分原始提示词、设计解读、实际源码和后补说明，避免把解读当作真实生成记录。用户要求复现时尊重指定视觉；用户要求借鉴时说明保留哪些原则、如何适配当前场景。

## 验证并交付

按当前项目方式构建和运行，检查真实内容下的主要页面、窄屏布局、关键交互、键盘操作、减少动态、可读性及资源加载。对照选中案例检查设计依据是否落实；同一任务的材料来自同一会话 SHA，刷新后需要重新确认候选与资料。

交付时列明引用的案例 ID、上游版本、完成的适配和实际验证结果。[Agent 协议说明](https://github.com/MIBXR/design-atlas/blob/master/AGENT.md) 与 `agent/catalog.json`、`agent/cases/<id>.json` 提供直接读取入口；当前项目的运行结果决定交付是否完成。
