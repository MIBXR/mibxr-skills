---
name: design-atlas
description: 从 Design Atlas 检索前端设计案例，读取完整源码、提示词与设计上下文，并适配真实网站需求。用于寻找网页风格参考、按指定案例构建页面或比较设计方向；网站案例库维护使用其仓库说明。
---

# Design Atlas 前端设计参考

把设计案例作为可追溯的参考，结合当前产品、内容和技术栈完成网站。完整案例由 [MIBXR/design-atlas](https://github.com/MIBXR/design-atlas) 维护；本技能只保存工作流、检索工具和上游版本锁，人类预览网站继续保留。

## 直接获取资料

使用本技能内的 `scripts/atlas.py`（Python 3，仅标准库）。以下命令以技能目录为当前目录；也可使用脚本的实际绝对路径。命令输出 UTF-8 JSON。

```bash
python scripts/atlas.py info
python scripts/atlas.py search "产品 极简" --limit 3
python scripts/atlas.py search "" --category "产品" --limit 10
python scripts/atlas.py show apple-product --source
python scripts/atlas.py export apple-product --out <新的目标目录>
```

`search` 返回匹配关键词的元数据和命中字段；没有结果时换为更短的关键词或列出相关分类，再根据真实需求选择。`show` 返回完整案例上下文，`--source` 同时返回经 SHA-256 核验的完整代码。`export` 保留仓库相对目录并核验全部文件，目标目录必须尚不存在；`--code-only` 仅下载源码和上下文，`atlas-export.json` 明确列出未下载的素材和预览，运行 Demo 前再取得所需媒体。用当前环境的静态 HTTP 服务器服务导出根目录，再打开输出中的 `entrypoint`。

已有本库 checkout 时，在子命令前加 `--local-root <checkout>` 可离线读取同一接口；输出以本地内容版本标识来源，不把未提交修改声称为锁定 commit。锁定的远程版本可用浏览器直接读取 [Agent 协议说明](https://github.com/MIBXR/design-atlas/blob/main/agent/README.md)，具体资料入口为 `agent/catalog.json` 与 `agent/cases/<id>.json`。

`upstream.lock.json` 固定远程仓库和完整 Git commit，资料始终从该 commit 获取。需要新版案例时，先用 `--ref <完整 commit>` 验证 `info`、候选的 `show --source` 和一次导出，再按本次更新范围修改版本锁或升级技能版本。脚本不写安装目录，不自动追随 `main`。

## 找到适合当前任务的案例

先读取当前项目和用户给出的内容，确定页面用途、主要使用者、内容密度、所需交互、技术栈及已有设计约束。用户已经选定案例时，直接按案例 ID 获取完整材料；寻找方向时，以用途与视觉要求检索并比较少量候选，说明它们适合当前任务的具体理由。

候选摘要用于选择。开始实现前读取选中案例的完整源码、原始提示词、设计解读和相关上下文，形成包含案例 ID、上游 commit、采用的原则及适配方式的短设计依据。每份资料的路径与可用性以返回的清单为准；缺失材料标明缺失。

同时读取 `webNotes.content`：它保留同一版本 `atlas.js` 实际渲染的案例详情右侧说明 HTML，覆盖设计机制、交互、约束、Tokens、Prompt 和来源证据。把网页说明与完整 `entry`、`documents` 对照后取材，保留来源的采集／理论核验日期、近似与未验证标记。发生差异时先检查是否混用了网页与数据版本，再取得同一 commit 的材料；仍有差异时列出具体字段与说明，按本次任务修复或报告。

## 把参考变成当前产品

从案例提取信息层级、布局节奏、色彩、字体、组件状态、交互和响应式行为，再应用到当前真实内容与功能。保留已有项目结构和用户确认的约束；所需模块根据任务实现。案例中的品牌、占位内容、外部素材和模拟行为各有来源，按当前产品替换或核实。

读取资料时区分原始提示词、设计解读、实际源码和后补说明，避免把解读当作真实生成记录。用户要求复现时尊重其指定视觉；用户要求借鉴时说明保留哪些设计原则、如何适配当前场景。

## 验证并交付

按当前项目方式构建和运行，检查真实内容下的主要页面、窄屏布局、关键交互、键盘操作及可读性。对照选中案例检查设计依据是否落实；同一任务的资料始终来自同一上游 commit。

交付时列明引用的案例 ID 与上游版本、完成的适配及实际验证结果。来源入口、预览和 Agent 获取通道各承担自己的用途：视觉预览帮助判断，完整资料支撑实现，当前项目的运行结果决定交付是否完成。
