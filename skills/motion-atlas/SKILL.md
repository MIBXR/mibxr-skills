---
name: motion-atlas
description: 从 Motion Atlas 选择影像视频、交互操作台与交互展示台的动态设计案例和巧思，自动取得节拍表、动效 Token、实现／视频生成 Prompt 与可逐帧渲染的 Demo 源码，用于制作有节奏和动感的动态视频、操作台或展示台；库维护使用其仓库说明。
---

# Motion Atlas 动态视觉参考

从完整案例选择时间结构与视觉语言，从巧思选择可独立借用的动效机制，再结合当前内容制作动态视频、可操作的界面或展示台。案例和巧思由 [MIBXR/motion-atlas](https://github.com/MIBXR/motion-atlas) 维护：每个案例拆成镜头、信息层、文字、转场与声音轨道，附节拍表、能量曲线、动效 Token、三段 Prompt（实现、视频生成、负向约束）和零依赖 Demo。本技能保存工作流与轻量检索工具。用户无需预先知道 ID，也无需手动复制源码或 Prompt。

## 通用约束

选择方案和实现时都应用以下约束；用户要求复现指定作品时，也先识别冲突并说明必要的适配。

- **文字可读性**：所有可见文字的最终渲染字号至少 12px，包括 HUD、时间码、字幕、Canvas 与 SVG 中缩放后的文字；不能用容器缩放把文字压到下限以下。12px 是下限，主要信息按观看距离选择更大字号。确需更小字号时，先说明原因与范围并获得用户同意。
- **SVG 图标**：播放、暂停、声音、方向等功能图标使用 SVG，优先复用项目已有图标；不以 Unicode 字符、Emoji 或图标字体替代。纯图标控件提供可访问名称。
- **减少动态**：遵守 `prefers-reduced-motion`：位移、缩放、震动改为透明度或直接出现；去掉频闪（每秒超过 3 次的闪烁）；自动播放的长动画停在能读懂的关键帧。节拍信息不只靠运动传达。
- **声音**：默认静音，由用户主动开启；提供可见的静音开关。
- **版权**：不使用第三方作品的画面、角色、标志、音乐或字体文件；复刻游戏界面时替换专有名词，只借鉴结构、节奏与参数。

## 建立本次取材会话

使用 `scripts/atlas.py`（Python 3，仅标准库）。新会话先读取上游仓库的默认分支及最新完整 Git SHA；案例与巧思共享这次会话的 SHA，后续检索、读取和导出保持一致。目录、资料包与每个文件都按 SHA-256 校验。

在用户当前项目的 `work/` 中选一个会话 JSON 路径，每次调用都传给 `--session`；脚本不向技能安装目录写状态。离线的 `--local-root CHECKOUT` 读取本地 Motion Atlas 工作树，不能与 `--session` 或 `--ref` 同用；`--ref FULL_COMMIT` 复现指定版本。下例中的 `ATLAS_SCRIPT` 是技能脚本的实际路径，`SESSION_FILE` 是用户工作目录中的 JSON 路径；输出 UTF-8 JSON，全局参数放在子命令前。

```bash
python ATLAS_SCRIPT --session SESSION_FILE info
python ATLAS_SCRIPT --session SESSION_FILE search "" --limit 100
python ATLAS_SCRIPT --session SESSION_FILE search "地图 旅行" --carrier video --limit 5
python ATLAS_SCRIPT --session SESSION_FILE search "" --evidence observed --seekable
python ATLAS_SCRIPT --session SESSION_FILE show map-pilgrimage
python ATLAS_SCRIPT --session SESSION_FILE show map-pilgrimage --source
python ATLAS_SCRIPT --session SESSION_FILE export map-pilgrimage --out NEW_DIRECTORY
python ATLAS_SCRIPT --session SESSION_FILE pattern-search "" --limit 100
python ATLAS_SCRIPT --session SESSION_FILE pattern-search "遮罩" --type transition
python ATLAS_SCRIPT --session SESSION_FILE pattern-search "" --role foundation --carrier console
python ATLAS_SCRIPT --session SESSION_FILE pattern-search "" --case phantom-battle
python ATLAS_SCRIPT --session SESSION_FILE pattern-show shape-wipe --source
python ATLAS_SCRIPT --session SESSION_FILE pattern-export shape-wipe --out NEW_DIRECTORY
python ATLAS_SCRIPT --session SESSION_FILE refresh
```

`info` 返回当前版本、数量、分类表（载体、来源、巧思类型、证据等级、组合职责）与 render(t) 协议说明；过滤值以它返回的分类表为准。空查询读取完整目录；`hasMore` 为 `true` 时保持同一会话、查询与过滤，把 `--offset` 增加本次 `limit` 继续读取。关键词用空格分隔，中英文都可以；分数只用于排序。需要后来新增的内容时显式 `refresh`，刷新失败保留原会话。

## 理解资料

- **载体** `carriers`：`video` 影像视频（成品是一段视频，全部写在时间轴上）、`console` 交互操作台（输入 → 反馈 → 余波 → 回程）、`showcase` 交互展示台（期待 → 揭示 → 停留 → 收尾）。一个案例可属于多种载体。
- **证据等级** `evidence`：`observed` 逐帧或源码实测；`adapted` 本地转译；`inferred` 依据公开资料推断、数值为拟合，复刻原作时必须向用户说明并建议用实机录像核验；`original` 本库原创设计语言。
- **案例字段**：`rhythm.beats`（节拍表，`t` 为 Demo 秒数）、`energy`（0–1 能量曲线）、`layers`（分轨）、`tokens.motion`（曲线、时长、BPM 等动效参数）、`composition`（色彩、字体、版式、影像、动效、声音、节奏的设计说明）、`interaction`、`prompt`、`videoPrompt`、`negativePrompt`、`migration`（改哪个配置项、怎么改）、`patternIds`。`documents.research` 是逐帧研究笔记，含观察方法、与原作的差异和验证记录。
- **巧思字段**：`mechanism`、`trigger`、`effect`、`timing`、`accessibility`、`composition.role`（`foundation` 骨架、`support` 支撑、`accent` 点睛）、`pairsWellWith`、`conflicts`、`sources[].evidence`。

## 选择与组合

用户只问库里有什么时，浏览完整目录，按载体与巧思类型介绍。需要制作时，先明确：成品形态（视频文件、网页内动态、可操作界面）、时长或交互流程、内容素材、品牌约束、技术栈与是否需要声音。用载体、内容关键词和体验类型检索，比较少量候选，说明能借用的节奏结构与适配代价。

先看节拍表与能量曲线是否符合内容的起伏，再看视觉语言。组合巧思时：一个作品通常只有 1 个骨架，配 2–4 个支撑、1–2 个点睛；检查 `pairsWellWith` 与 `conflicts`；同一时刻只让一条轨道（镜头、信息层、文字、特效）当主角；高潮前留低谷或停顿，结尾给回落时间。这些关系是设计建议，需要结合当前内容验证。

候选摘要只用于选择。实现前对最终案例执行 `show --source`、对最终巧思执行 `pattern-show --source`，形成包含 ID、上游 commit、职责与适配方式的简短设计依据。

## 取得材料并实现

需要可运行参考时执行 `export` 或 `pattern-export`，目标目录必须尚不存在。导出保留仓库相对路径：Demo 源码、`motion-kit.js` 副本、预览图，以及 `prompts/` 下的 Prompt 文档与 `docs/research/` 下的研究笔记；`atlas-export.json` 记录资料包、文件摘要与上游版本。`--code-only` 跳过预览图并列明未下载文件。用任意静态 HTTP 服务器服务导出根目录，打开输出的 `entrypoint`；地图类 Demo 需要联网加载瓦片。

迁移时保留时间结构与动效参数，替换内容与品牌：案例的内容集中在 `config.js`，巧思集中在 `index.html` 顶部的 `CONFIG`；按条目的 `migration` 修改文案、配色、时刻表与素材。换色时保持原方案的明度节奏。区分原始观察、设计解读与本地拟合数值，按证据等级表述。

时间驱动的作品遵守 render(t) 协议：画面只依赖时刻 `t`；随机数用 `MotionKit.rng(seed)` 并按 `t` 派生；用 `MotionKit.timeline` 包装并 `MotionKit.expose()` 暴露 `window.__motion = { duration, markers, seek(t), play(), pause(), on(fn) }`；`?embed` 隐藏控制条，`?render` 关闭自动播放，`?t=秒` 定位。可交互作品用“事件列表推导状态 + 自动驾驶时间轴”：真实输入切换到实时时钟，外部 seek 或播放回到自动驾驶，这样同一份代码既能操作也能录制。

只需要视频生成 Prompt 时，以案例的 `videoPrompt` 为底稿，保留时长、节拍、镜头语言与转场，替换主题与配色，再合并 `negativePrompt`；需要精确出现的文字建议后期叠加。

## 出片与参考分析

逐帧渲染与参考视频取帧使用上游仓库的 Node 脚本（Node.js 22+，本机 Edge 或 Chrome，无需安装依赖）。在任务工作区克隆 `https://github.com/MIBXR/motion-atlas`，检出会话的 `ref`，然后：

```bash
node scripts/render.mjs demos/cases/beat-lyric/index.html --fps 30
node scripts/render.mjs http://localhost:PORT/path/to/index.html --fps 30 --w 1920 --h 1080
node scripts/frames.mjs reference.mp4 --every 2
```

`render.mjs` 逐帧 seek 并截图，PATH 上有 ffmpeg 时自动合成 MP4，否则保留帧序列并打印合成命令；渲染不录制 WebAudio 声音，配乐按节拍表在剪辑软件中对齐。`frames.mjs` 生成带时间码的接触表，用于观察参考视频；参考素材与取帧结果只留在任务工作区，不提交到作品仓库。

## 验证并交付

按项目方式运行，检查：从 0 秒 seek 到结尾无报错；在节拍表的每个关键时刻截图，对照设计依据；桌面与窄屏下文字不溢出、不重叠；键盘操作与焦点；减少动态后的状态；声音的开启、静音与重复触发。在实际渲染中核验 12px 下限（含 Canvas 与 SVG 缩放后的字号）与 SVG 图标；静态搜索只能辅助。

交付时列明引用的案例与巧思 ID、上游版本、组合职责、完成的适配、证据等级为 `inferred` 的部分，以及实际验证结果与未验证项。[Agent 协议说明](https://github.com/MIBXR/motion-atlas/blob/main/AGENT.md) 与 `agent/catalog.json`、`agent/cases/<id>.json`、`agent/patterns/<id>.json` 提供直接读取入口。
