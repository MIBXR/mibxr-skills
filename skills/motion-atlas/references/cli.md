# Motion Atlas CLI

## 建立取材会话

使用本 skill 的 `scripts/atlas.py`（Python 3，仅标准库），读取 `MIBXR/motion-atlas` 的 Agent 协议，输出 UTF-8 JSON。全局参数放在子命令前；下例的 `ATLAS_SCRIPT` 是脚本实际路径，`SESSION_FILE` 是用户项目 `work/<任务名>/motion-session.json`，`NEW_DIR` 是尚不存在的导出目录。

远程首次使用 `--session SESSION_FILE` 时，解析 GitHub 默认分支的最新完整 Git SHA。案例、巧思和素材共享该 SHA，后续检索、查看、取材和导出持续传同一会话路径。会话保存 `repository`，跨仓库复用会报错；状态写在用户工作区，不写入 skill 安装目录。

```bash
python ATLAS_SCRIPT --session SESSION_FILE info
python ATLAS_SCRIPT --session SESSION_FILE search "" --limit 100 --offset 0
python ATLAS_SCRIPT --session SESSION_FILE search "地图 节奏" --limit 5
python ATLAS_SCRIPT --session SESSION_FILE search "" --kind cases --carrier video
python ATLAS_SCRIPT --session SESSION_FILE search "" --carrier console
python ATLAS_SCRIPT --session SESSION_FILE search "转场" --kind patterns --type transition --limit 5
python ATLAS_SCRIPT --session SESSION_FILE search "" --kind materials
python ATLAS_SCRIPT --session SESSION_FILE show motion-showreel
python ATLAS_SCRIPT --session SESSION_FILE export web-video-presentation --out NEW_DIR --code-only
python ATLAS_SCRIPT --session SESSION_FILE show archive-os
python ATLAS_SCRIPT --session SESSION_FILE show archive-os --source
python ATLAS_SCRIPT --session SESSION_FILE export map-pilgrimage --out NEW_DIR
python ATLAS_SCRIPT --session SESSION_FILE export map-pilgrimage --out NEW_DIR --code-only
```

## 参数与检索

```text
atlas.py [--session PATH] [--ref FULL_COMMIT] [--local-root CHECKOUT] COMMAND
info
refresh
search QUERY [--kind cases|patterns|materials] [--carrier video|console] [--type TYPE] [--limit N] [--offset N]
show ID [--source]
export ID --out NEW_DIR [--code-only]
```

- `search` 默认在案例、巧思和素材中检索；空查询列目录。`--kind` 筛选 `cases`／`patterns`／`materials`。
- `--carrier` 匹配目录实际的 `carriers[]`：`video`（影像视频）、`console`（交互操作台）。
- `--type` 匹配巧思的 `types[]`：`composition`（画面构成）、`type-motion`（文字动效）、`transition`（转场）、`camera`（镜头与空间）、`feedback`（交互反馈）、`rhythm`（节奏与时序）、`hud`（信息层 HUD）、`texture`（质感与后期）、`sound`（声音）。案例没有 `types[]`，带类型筛选不会命中案例。
- `--limit` 为 1–100；`--offset` 为非负整数。`hasMore=true` 时保持查询、过滤与会话不变，将 offset 增加本页 limit 后继续，直到 `hasMore=false`。
- 中文和英文关键词用于检索标题、摘要、标签等内容，排序分数只用于召回排序，是否适用仍按简报判断。

`show ID` 返回完整案例或巧思资料包、Prompt、入口、文件清单和上游信息；`--source` 再读取 Demo 的 HTML／CSS／JS 源码，排除共享的 `motion-kit.js`。来源案例的读取与使用见 [selection.md](selection.md)。
素材 ID 返回素材包，包含完整条目、工作流、skill 原文、README 与快照文件清单；选用前读取原文和许可。

## SHA、离线与刷新

`info` 显示当前上游信息与案例、巧思、素材数。无会话时读取最新默认分支；已有会话时复用其 SHA。`--ref` 只接受完整 40 位 Git commit，不接受分支名或短 SHA；已有会话与显式 ref 不同会报错，复现另一提交时使用独立会话。

```bash
python ATLAS_SCRIPT info
python ATLAS_SCRIPT --ref 2f63ac64f5c5d31f58d516f1794e1da964179ec6 search "" --limit 100
python ATLAS_SCRIPT --local-root C:/Users/mibxr/Code/MIBXR/motion-atlas info
python ATLAS_SCRIPT --local-root C:/Users/mibxr/Code/MIBXR/motion-atlas search "转场" --kind patterns
python ATLAS_SCRIPT --session SESSION_FILE refresh
```

`--local-root CHECKOUT` 读取本地当前工作树，不能与 `--session` 或 `--ref` 同用；本地输出的 `provenance.ref` 为 `null`。
`refresh` 必须带 `--session`，不与 `--ref` 或 `--local-root` 同用。它重新解析默认分支提交，读取成功后替换会话；失败保留原会话。刷新后同一任务的材料都取自新的 SHA。
默认分支解析失败会报错；已有会话、显式 `--ref` 与离线 `--local-root` 分别可用。

`upstream.lock.json` 保存仓库、目录路径、schema 版本与已验证基线；基线不限制默认发现新增条目。当前 Agent catalog 和资料包的 schemaVersion 为 1，读取 `agent/catalog.json`、`agent/cases/<id>.json`、`agent/patterns/<id>.json` 与 `agent/materials/<id>.json`；素材目录为 `agent/materials.json`。

## 导出与运行

`export ID --out NEW_DIR` 按资料包 `files[]` 下载全部文件，保留仓库相对目录，目标目录必须不存在。根目录的 `atlas-export.json` 保留完整资料包 `bundle`（含 `documents.prompt`）、入口 `entrypoint`、上游信息 `provenance`、实际下载清单 `files`、未下载清单 `notDownloaded` 以及 `codeOnly` 标记；不额外生成根级 `PROMPT.md`、`README.md` 或 `entry.json`。
素材导出按同样规则保存素材包与 `agent-skills/<id>/` 下的 skill 快照；`--code-only` 仍按下面的扩展名白名单筛选，未下载文件保留在清单中。

`--code-only` 仅下载扩展名属于 `.html`、`.htm`、`.js`、`.mjs`、`.cjs`、`.css`、`.json`、`.md`、`.txt`、`.svg`、`.glsl`、`.frag`、`.vert`、`.wgsl`、`.xml`、`.csv` 的代码与文本文件，扩展名不区分大小写；其余文件记录在 `notDownloaded`，每项含 `path` 与 `bytes`。未带该参数时下载全部文件，`notDownloaded` 为空数组。图片、音频、字体等依赖可能因此未下载，运行前按清单补齐。

导出后从根目录启动静态 HTTP 服务器，打开清单的实际入口；带地图、字体和异步资源的 Demo 不用 `file://` 代替运行验证：

```bash
python -m http.server 4331 --bind 127.0.0.1 --directory NEW_DIR
```

例如入口为 `demos/cases/map-pilgrimage/index.html` 时打开 `http://127.0.0.1:4331/demos/cases/map-pilgrimage/index.html`。渲染工具不在当前导出文件清单中，关键帧条、短片段与完整渲染的方法见 [preview.md](preview.md)。
