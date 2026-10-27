# Web 感受词翻译表

用户给出感受词时，先按表调整并展示结果，不反过来问“具体指什么”。一次反馈最多调两到三个参数；先保留用户没有否定的内容与任务。

依据中的 ID 是 Web Atlas 的案例，可用 `show ID` 查看。

甲为可能触发该反馈的参数侧，乙为相反参数侧。数值取自源案例的局部取值或可试区间；色值按角色配对，普通网页 UI 字号至少 12px。

| 用户说 | 先调（参数 → 方向；有证据的写出数值范围） | 别误调（容易被一起改坏的参数） | 依据（案例对） |
| --- | --- | --- | --- |
| 太冷 | 基底与强调色往暖纸/陶土方向试：#f4f0e4／#b17451，或#f5f5ef／#d97757；先换这两种角色。 | 保留文字对比、产品界面与品牌素材原色。 | linear-workflow ↔ claude-platform；line-art ↔ hand-drawn |
| 太甜 | 先降低浅彩/可爱插画的界面占比，再收敛圆角；若曲率在抢语气，可从24/48px试向4–12px的工具侧。 | 插画承担世界观时保留身份；触控边界与正文对比不随之缩小。 | blue-archive ↔ arknights-world；google-material ↔ stripe-platform |
| 不够高级 | 先减与内容无关的装饰，再收敛UI基础色盘；可试Swiss的3色或Apple的4个色盘条目，不限制摄影本身色数。 | 不把“高级”当贵价/暗色/无内容的同义词；真实产品证据、可读性保留。 | persona-kinetic ↔ apple-product；shape-morph ↔ swiss-grid |
| 太乱 | 减少持续装饰运动，换态按一个主要信息顺序推进；先停不承担解释的星光/背景层，再让索引与内容同一状态更新。 | 不能把多个独立状态误合并；保留角色、文件或参数的真实对应关系。 | persona-kinetic ↔ line-art；endfield-industrial ↔ met-museum |
| 太空 | 把主要行动/事实提前到视觉附近；内容确有目录时增加可扫描分组，如两列结果或三类条件，而不是填装饰。 | 保留主图完整与正文呼吸；没有更多真实内容就不编卡片。 | blue-archive ↔ digital-dunhuang；rijksmuseum-art ↔ met-museum |
| 太平淡 | 加强一个主体轮廓与局部强调色的反差；蓝灰#607ca4可对照酸黄#e3ef85的小范围强调，或大几何构成的尺度差。 | 正文颜色与背景仍成对；不要把每项都变成主角或给阅读正文套装饰字体。 | met-museum ↔ bauhaus-geometry；line-art ↔ shape-morph |
| 太用力 | 先降低全屏位移/章交接的控制感，再取消非必要持续装饰；可把1000ms全屏wipe方向退回原生阅读，保留局部有用反馈。 | 世界场景的身份与章节位置要保留；暂停不等于删掉事实内容。 | arknights-world ↔ met-museum；persona-kinetic ↔ hand-drawn |
| 太慢 | 先让文字/行动立即到达，再缩短主动选择的过渡；局部状态可试220–400ms，替代1200ms默认形变或延迟标题的等待感。 | 不同机制不能统一套时长；影片原速、真实进度和按需说明不为此加速。 | zelda-world ↔ uma-musume；shape-morph ↔ bauhaus-geometry |
| 太快 | 先增加阅读停留，再延长整块换态；摄影周期可由3600ms试向6000ms；人物100ms淡换可对照1000ms整轨的慢端。 | 自动周期、过渡时长和影片速度分开；不为变慢增加强制输入锁。 | genshin-world ↔ blue-archive；fuji-rock ↔ design-sight |
| 太严肃 | 增加与产品有关的人物/创作线索，再让边界或纸张材料稍有手工感；只动图像语气与轮廓两项。 | 不把专业参数、可读正文或稳定点击边界改成玩具；普通UI至少12px。 | linear-workflow ↔ notion-editorial；line-art ↔ hand-drawn |
| 没记忆点 | 先建立一组与内容绑定、能反复出现的主体轮廓，再使状态变化沿用同一身份；可参考建筑局部或同一组几何单元，而非另加随机Logo。 | 不以新增装饰数量替代识别；不能声称这样已提升真实记忆率。 | met-museum ↔ palace-museum；line-art ↔ shape-morph |
| 太硬 | 优先增加容器曲率：可试17–24px内容/视频面板，行动需要胶囊时参考48px；按部件角色各改一处。 | 保留操作尺寸、品牌方标和海报原比例；不是整页统一圆角。 | swiss-grid ↔ google-material；rijksmuseum-art ↔ claude-platform |
| 太软 | 优先收紧窗口/按钮曲率：可试4–12px，或方角海报配细边行动；清楚分开内容边界与装饰。 | 不缩小触控区，不提高所有边框粗度；图像与品牌自身的圆形仍可保留。 | google-material ↔ stripe-platform；claude-platform ↔ met-museum |

## 近义词映射

用户的说法不在上表时，先按下面的映射找最近的一行；仍然对不上时，按第 6 步把反应拆成具体元素，再决定调哪些参数。

| 用户说 | 先看 |
| --- | --- |
| 太廉价、太土 | 不够高级 |
| 太幼稚、太卡通 | 太甜 |
| 太素、没亮点 | 太平淡 |
| 太花、太吵 | 太乱 |
| 太拖、等太久 | 太慢 |
| 太闷、太正经 | 太严肃 |
| 太浮夸、太炫 | 太用力 |
