# Web Atlas 命令与取材会话

## 建立本次取材会话

使用 `scripts/atlas.py`（Python 3，仅标准库）。新会话先读取上游仓库的默认分支及最新完整 Git SHA；案例、巧思与素材共享这次会话的 SHA，后续探索、筛选、取材和导出保持一致。

远程取材时，在用户当前项目的 `work/` 中选一个会话 JSON 路径，每次调用都传给 `--session`。脚本不向技能安装目录写状态。离线的 `--local-root CHECKOUT` 读取当前工作树，不能与 `--session` 或 `--ref` 同用；需要复现时使用已提交的版本。下例中的 `ATLAS_SCRIPT` 是技能脚本的实际路径，`SESSION_FILE` 是本次用户工作目录中的 JSON 路径；命令输出 UTF-8 JSON，所有全局参数放在子命令前。

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
python ATLAS_SCRIPT --session SESSION_FILE material-search "" --limit 100 --offset 0
python ATLAS_SCRIPT --session SESSION_FILE material-search "shader 背景" --limit 5
python ATLAS_SCRIPT --session SESSION_FILE material-search "" --type component-library
python ATLAS_SCRIPT --session SESSION_FILE material-search "" --category "组件与效果"
python ATLAS_SCRIPT --session SESSION_FILE material-show MATERIAL_ID --source
python ATLAS_SCRIPT --session SESSION_FILE material-export MATERIAL_ID --out NEW_DIRECTORY
```

按当前任务选择 `search`（完整案例）、`pattern-search`（独立巧思）或 `material-search`（内容素材），空查询读取目录。若 `hasMore` 为 `true`，保持同一会话、查询与过滤，把 `--offset` 增加本次 `limit` 继续读取，直到 `hasMore` 为 `false`；单页上限为 100，目录总量不限。查询支持中文和英文关键词，输出命中字段、适用场景与谨慎使用项；分数用于排序，适合程度结合真实需求判断。巧思可按单个 `--type` 体验类型、`--category` 功能分类、`--case` 来源案例共同过滤；`experienceTypes` 可含多个类型，命中其中一个即符合类型过滤。素材按其 `type`（如 `component-library`）与功能分类过滤，类型由目录中的实际标注决定。

体验类型由上游逐项标注：`visual` 是排版、色彩、装饰和形状等静态视觉机制；`micro-motion` 是按钮、卡片等局部反馈或辅助动效；`page-motion` 是首屏、滚动叙事、页面过渡等主体动效；`sound` 是背景音乐和操作音；`structure` 是内容组织、导航和信息关系。按当前产品的问题筛选，不要求每个案例具备全部类型，也不为凑类型拆分机制。声音适用于游戏、品牌叙事等确有听觉需求的场景，结合声音巧思包的来源观察与核验边界选择。

需要取得后来新增的案例、巧思或素材时，显式刷新会话后重新检索：

```bash
python ATLAS_SCRIPT --session SESSION_FILE refresh
```

刷新解析默认分支的新 Git 提交，读取该版本的案例目录后替换会话；失败保留原会话。各命令只读取对应目录和实际取用的内容，巧思取材同时读取其来源案例。无需会话的 `info` 查看当前最新版本及各目录的数量。默认解析失败会明确报错；已有会话、`--ref FULL_COMMIT` 复现模式及 `--local-root CHECKOUT` 离线模式各自可用。后两种模式的全局参数也放在子命令前。`upstream.lock.json` 保存上游配置和已验证基线，基线不限制默认发现新增内容。

## 取得完整材料与预览

需要可运行参考时执行 `export`、`pattern-export` 或 `material-export`，按固定的 Git 提交读取文件，保留仓库相对目录。目标目录必须尚不存在。巧思导出自动取得相关案例的完整 demo、素材和上下文，`atlas-export.json` 保留巧思包、`sourceFiles`、来源案例包、文件路径与上游版本；以原子机制的职责取材，完整 demo 用于理解页面关系。素材导出保留资源包、样例源码和许可上下文，目录中的实际文件由清单决定。各导出均支持 `--code-only` 仅下载源码与上下文，并列明未下载素材及预览。完整预览媒体按清单补齐，用静态 HTTP 服务器服务导出根目录，打开输出的 `entrypoint` 或 `entrypoints[].path`。

## 直接读取入口

[Agent 取材说明](https://github.com/MIBXR/web-atlas/blob/master/docs/agent.md) 与 `agent/catalog.json`、`agent/cases/<id>.json`、`agent/patterns.json`、`agent/patterns/<id>.json`、`agent/materials.json`、`agent/materials/<id>.json` 提供直接读取入口。
