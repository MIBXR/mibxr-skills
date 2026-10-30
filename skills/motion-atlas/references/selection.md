# Motion Atlas 选材与组合

## 读取完整条目

摘要只用来检索收敛。实现前执行 `show ID --source`，读取完整 `entry`（案例）或 `pattern`（巧思）、`documents.prompt`、`entrypoint` 与 `files[]`；巧思还带 `sourceCases`，按其案例 ID 读取来源案例，理解机制在完整时间线中的作用。

案例的 `rhythm.duration`、`rhythm.bpm`、`rhythm.beats` 与 `energy` 用来理解时长、节拍和能量起伏；巧思的 `trigger`、`effect`、`timing`、`markers`、`tokens`、`accessibility` 与 `avoid` 用来检查采用条件和限制。文件是否可逐帧定位以实际 `window.__motion` 协议为准。

## 组合职责

- `composition.role=foundation`：骨架，决定主视觉与信息层级，一个作品通常只有一个。
- `support`：支撑，承担一个区域的交互或信息。
- `accent`：点睛，短时、局部的强调，同一时刻不超过两个。

先定骨架，再给支撑与点睛分配清楚的区域、时段和职责。逐项检查 `composition.pairsWellWith`、`composition.conflicts`、`composition.notes`。
检查骨架是否唯一、点睛是否争抢注意力、触发条件和时间轴是否冲突。多个全屏状态、强镜头运动与高密度信息层同时出现时，说明取舍并减少竞争；画面和声音共用节拍表。

## Prompt 三段

资料包的 `documents.prompt` 是完整 Prompt 文档；条目里的 `prompt`、`videoPrompt`、`negativePrompt` 分别对应：

- **实现 Prompt**：把结构、布局、时间轴、参数与交互要求用于 HTML／CSS／JS 实现；结合实际源码、`tokens` 与 `migration` 读取。
- **视频生成 Prompt**：用于视频生成模型的镜头、节奏、画面与声音描述；替换为用户真实内容，并核对目标画幅和时长。
- **负向约束**：与采用的 Prompt 一起保留，检查禁止出现的视觉处理、叠加或素材使用方式。

字段缺失就说明条目未提供该段，不补写成上游原文。区分条目的 Prompt、实际源码与本次适配说明；借鉴时说明保留哪些原则、改变哪些参数，复现时尊重用户指定视觉。

## 来源与证据

条目没有 `observed`／`adapted`／`inferred` 证据等级字段，不替上游添加等级。`sourceCases`／`sources[].caseId` 表示来源案例关联，不等于对外部实物或来源的独立核验。
把自己看到的运行效果、从源码推断的机制与未验证内容分开表述，保留条目的原始来源和限制。第三方画面、音乐、字体可以随作品提交，附许可原文与出处署名。参考视频取帧与渲染输出留在工作区。
