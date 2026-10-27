# Motion 感受词翻译表

用户给出感受词时，先按此表局部调整，再展示结果；不要反过来问用户“具体指什么”。一次反馈最多调两到三个参数；所有方向都先服从已确认的目的、品牌和素材约束。

依据中的 Motion Atlas 案例或巧思 ID 可用 `show ID` 查看；`mg-styles-15:`、`video-shotcraft:` 开头的条目无需读取。

| 用户说 | 先调（参数 → 方向；有证据的写出数值范围） | 别误调（容易被一起改坏的参数） | 依据（案例对） |
| --- | --- | --- | --- |
| 太冷 | 强调色 → 从青冷方向试暖金/暖白（#00E5FF 对照 #E9D7A5）；缓动 → 减少硬直线性，试连续缓入缓出。 | 不要同时增加所有回弹；终端精确性、信息对比仍要保住。 | mg-styles-15:22-hud ↔ mg-styles-15:02-line-art；mg-styles-15:09-bauhaus ↔ mg-styles-15:01-flat-vector |
| 太甜 | 回弹/挤压 → 减少（对照约1.15尺度峰、10%形变与无overshoot）；配色数量 → 从5–6色试向单/双色收敛。 | 不要把饱和度全部拉灰；也不要删掉角色或笑点的语义。 | mg-styles-15:18-hanazi ↔ mg-styles-15:09-bauhaus；mg-styles-15:01-flat-vector ↔ mg-styles-15:02-line-art |
| 不够高级 | 配色关系 → 收敛到2–3邻近色或单/双色；标题入场幅度 → 从夸张尺度回弹试向透明度+约8px位移。 | 不要用慢速遮住关键信息，也不要把喜剧/扁平风格等同低质量。 | mg-styles-15:18-hanazi ↔ mg-styles-15:12-aurora-glass；mg-styles-15:01-flat-vector ↔ mg-styles-15:02-line-art |
| 太乱 | 配色数量 → 减少互相竞争的颜色（5–6或8–32色，对照单/双色或2–3色）。 | 不要盲删信息或让状态失去区别；像素调色板不等于实际同时用色。 | mg-styles-15:01-flat-vector ↔ mg-styles-15:02-line-art；mg-styles-15:20-pixel ↔ mg-styles-15:19-paperclip |
| 太平淡 | 事件节奏 → 加一个明确拍点动作（对照120BPM、0.5s/拍）；形态或声音重音 → 在同一高光二选一加强。 | 不要整片都提高速度或增音量；保留高光前后呼吸。 | mg-styles-15:12-aurora-glass ↔ mg-styles-15:09-bauhaus；mg-styles-15:02-line-art ↔ mg-styles-15:07-liquid |
| 太用力 | 入场幅度 → 降低尺度峰，试透明度+8px位移；故障频率 → 从每秒1–2次收敛到真正需要的节点。 | 不要把所有运动消掉；关键动作的因果、主标题层级仍清楚。 | mg-styles-15:18-hanazi ↔ mg-styles-15:12-aurora-glass；mg-styles-15:10-synthwave ↔ mg-styles-15:02-line-art |
| 太慢 | 首个有效信息到达 → 提前（案例对照4s片名与22s阵列）；独立事件间隔 → 缩短，先加有效变化而非全片加速。 | 不要把20–40s背景漂移周期误当镜头停留，也不要削掉必要阅读。 | archive-os ↔ map-pilgrimage；mg-styles-15:12-aurora-glass ↔ mg-styles-15:09-bauhaus |
| 太快 | 主事件间隔 → 拉开（4–6s事件，对照7.5–13s终端阶段）；持续背景运动 → 放慢，让重要文字有静止窗口。 | 不要只降低输出帧率；长周期背景与操作响应时长分开处理。 | map-pilgrimage ↔ archive-os；mg-styles-15:09-bauhaus ↔ mg-styles-15:12-aurora-glass |
| 太严肃 | 形体弹性 → 在一个主体试少量挤压伸展（风格参照约10%）；字形或提示音 → 从仪表式换成更亲和的一类。 | 不要把全部信息改成圆胖字；精确数值和警示含义仍稳定。 | mg-styles-15:09-bauhaus ↔ mg-styles-15:01-flat-vector；mg-styles-15:22-hud ↔ mg-styles-15:18-hanazi |
| 太幼稚 | 回弹/挤压 → 收敛到无overshoot；字形与配色 → 从多描边高饱和试向细线、单/双色。 | 不要损失角色识别或变得冷硬；只改装饰性的弹性。 | mg-styles-15:01-flat-vector ↔ mg-styles-15:09-bauhaus；mg-styles-15:18-hanazi ↔ mg-styles-15:02-line-art |
| 太硬 | 主缓动 → 从steps/linear试连续ease-out（流体参照0.22,1,0.36,1）；次级跟随 → 加少量2–3帧延迟。 | 像素风整像素与机械动作可能是必要约束；先检查是否允许改变。 | mg-styles-15:09-bauhaus ↔ mg-styles-15:01-flat-vector；mg-styles-15:20-pixel ↔ mg-styles-15:07-liquid |
| 太软 | 回弹/拖尾 → 减少，试无overshoot；边缘清晰度 → 降低流体模糊，建立清楚落点。 | 不要给连续流体强套像素steps；保留所选媒介的基本形态。 | mg-styles-15:01-flat-vector ↔ mg-styles-15:09-bauhaus；mg-styles-15:07-liquid ↔ mg-styles-15:20-pixel |
| 太碎 | 故障/抖动频率 → 减少（参照±2px、6–12fps及1–2次/s故障）；镜头连续性 → 让主运动跨过小事件而不中断。 | 不要用补帧抹掉有意手工质感；也不要只延长转场却留住同样多突变。 | mg-styles-15:06-collage ↔ mg-styles-15:02-line-art；mg-styles-15:10-synthwave ↔ mg-styles-15:12-aurora-glass |
| 太吵 | 提示音触发密度 → 减少逐字和重复操作声；音色种类 → 从警示集合收敛为必要的一两类，先留关键动作。 | 不凭8类/1类音色集合推响度或同时层数；别只压总音量而留着所有提示。 | alert-reroute ↔ film-grain；boot-typing ↔ chapter-frame |

没有两组足够对照的“太廉价、太空、太老气、没记忆点、太拖、不够燃”不进入调整表，原因见工作底稿表 F。

## 近义词映射

用户的说法不在上表时，先按下面的映射找最近的一行；仍然对不上时，按第 6 步把反应拆成具体元素，再决定调哪些参数。

| 用户说 | 先看 |
| --- | --- |
| 太拖、节奏松 | 太慢 |
| 不够燃、没高潮 | 太平淡（并检查能量曲线是否有明确峰值） |
| 太廉价 | 不够高级 |
| 太空、太单调 | 太平淡 |
| 没记忆点 | 太平淡（并检查结尾是否有可复述的一个画面或一句话） |
| 太卡通 | 太幼稚 |
| 太花 | 太乱 |
| 太晃、看得累 | 太碎 |
