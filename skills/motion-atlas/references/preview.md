# Motion Atlas 草样与逐帧渲染

## 工具从哪里来

本 skill 的 `export` 按资料包的 `files[]` 取材；当前资料包只列 Demo 与预览文件，**不包含** `scripts/render.mjs`、`scripts/shot.mjs` 或其依赖。
从 Motion Atlas 仓库的同一上游 SHA 取得完整工具目录，或使用已有本地仓库；`--local-root` 只读取该工作树，不下载渲染工具。渲染脚本还依赖 `scripts/lib/cdp.mjs`、`scripts/lib/catalog.mjs` 等，不能只拿单个 `.mjs`。
需要 Node.js ≥ 22 和本机 Edge／Chrome／Chromium；未被自动找到的浏览器用 `BROWSER_PATH` 指定。合成 MP4 需要可用的 ffmpeg；没有时渲染器保留帧序列并打印合成命令。

以下以本地仓库 `C:/Users/mibxr/Code/MIBXR/motion-atlas` 为例，命令在 Git Bash 中运行。Windows 先核实 `command -v bash python node ffmpeg ffprobe` 和 `node --version`；复杂命令保存为 UTF-8、LF 的 `.sh` 文件，再用已定位的 `bash.exe` 执行。输出全部写到用户工作区，仓库只读；替换路径、ID 和时间点后用于当前项目。

```bash
ATLAS_SCRIPT=/c/Users/mibxr/Code/MIBXR/mibxr-skills/skills/motion-atlas/scripts/atlas.py
MOTION_ROOT=/c/Users/mibxr/Code/MIBXR/motion-atlas
PREVIEW_ROOT=/c/Users/mibxr/Code/MIBXR/_atlas-work/t4-skills/preview-test
python "$ATLAS_SCRIPT" --local-root "$MOTION_ROOT" export map-pilgrimage --out "$PREVIEW_ROOT/demo"
mkdir -p "$PREVIEW_ROOT/frames"
```

`demo` 目标目录必须不存在，重复演示时把 `PREVIEW_ROOT` 改成一个新目录。此处完整导出，不用 `--code-only` 丢掉运行所需媒体。按用户真实内容修改导出副本的 `config.js` 或 `CONFIG`。用单独的 Git Bash 终端从整个预览目录启动服务器，同时服务 Demo、关键帧和拼条页面；第二个终端也要将 `PREVIEW_ROOT` 设为同一个目录：

```bash
PREVIEW_ROOT=/c/Users/mibxr/Code/MIBXR/_atlas-work/t4-skills/preview-test
python -m http.server 4331 --bind 127.0.0.1 --directory "$PREVIEW_ROOT"
```

保留仓库相对路径后的入口为 `http://127.0.0.1:4331/demo/demos/cases/map-pilgrimage/index.html`，以 `demo/atlas-export.json` 的实际入口为准。端口占用时换空闲端口，并同步修改下文 URL。渲染器对本地文件路径限制在上游仓库内，导出副本或用户项目须用 HTTP URL；无需修改只读仓库。

## 已核实的时间轴接口

时间驱动作品通过 `MotionKit.expose(tl)` 提供 `window.__motion`：

- `duration`、`markers`、`time`、`playing`；`ready` 是预加载 Promise。
- `seek(t)` 返回 Promise，等待 `render(t)` 的异步工作；`pause()` 停止播放，`play()` 开始播放。
- `orient`、`orients` 与 `setOrient(o)`；后者返回 Promise。`orients=[]` 表示没有固定画幅舞台。
- 挂了乐谱时，`audio.renderWav({ from, to, sampleRate })` 离线输出 WAV 数据；否则 `audio=null`。

取帧顺序是：打开带 `?render=1&embed=1&orient=landscape` 的入口，等待 `window.__motion` 和 `ready`，调用 `pause()`，再对每个时刻 `await seek(t)` 后截图。真实画面必须只由 `t` 决定；异步地图、图片与字体就绪后再截图，不能用墙上时钟等待代替 seek。

## 关键帧条：6–8 帧

读取案例 `entry.rhythm.beats`；巧思先读已提供的 `pattern.markers`，未提供时读取 `window.__motion.markers`，或 `MotionKit.replay` 配置、拆分型顶部 `CONFIG` 中的事件时刻。条目提供能量曲线时结合它，在段落起点、主要信息到达、能量峰值和收尾各取代表帧；有进出与回程的机制，覆盖前态、峰值、完成和回程。时间点以当前改写后的节拍表为准，避免机械均匀抽样。
段落起点常是元素尚未显现的第一帧，取代表画面时要继续查看入场后的峰值或稳定态。`map-pilgrimage` 可取 `6、12.4、22、30.2、46、58` 秒，分别展示片名、抵达、卡片全屏、分屏对比、警示改道和结尾统计；这些时刻依据 `4、11.6、21、29.2、45、56` 秒的节拍起点及实际入场过程选择。改过时长或节奏后重选；需要验证回程时另取回程完成帧，不把这六帧当作全部状态验收。

`shot.mjs` 接收 HTTP URL，可重复 `--t`；多时刻输出为 `key-6.png`、`key-12.4.png` 等，输出父目录先创建：

```bash
node "$MOTION_ROOT/scripts/shot.mjs" 'http://127.0.0.1:4331/demo/demos/cases/map-pilgrimage/index.html?render=1&embed=1' --orient landscape --w 640 --h 360 --t 6 --t 12.4 --t 22 --t 30.2 --t 46 --t 58 --out "$PREVIEW_ROOT/frames/key.png"
```

用 Python 标准库生成六帧、两行三列的拼条页面，再用同一截图工具输出 PNG；时间点、标签和文件名保持一致：

```bash
python - "$PREVIEW_ROOT" <<'PY'
from pathlib import Path
import html
import sys
root = Path(sys.argv[1])
frames = [('6', '片名'), ('12.4', 'DAY 01 · 抵达'), ('22', '卡片全屏'), ('30.2', '分屏对比'), ('46', '警示改道'), ('58', '结尾统计')]
style = 'body{margin:24px;background:#121619;color:#f1eee7;font:16px/1.5 system-ui,sans-serif}main{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}figure{margin:0;background:#20262a}img{display:block;width:100%;aspect-ratio:16/9}figcaption{padding:8px 12px}'
cards = ''.join(f'<figure><img src="frames/key-{t}.png" alt="{html.escape(label)}"><figcaption>{t}s · {html.escape(label)}</figcaption></figure>' for t, label in frames)
(root / 'keyframes.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>6 Keyframes</title><style>' + style + '</style><main>' + cards + '</main></html>\n', encoding='utf-8')
PY
node "$MOTION_ROOT/scripts/shot.mjs" 'http://127.0.0.1:4331/keyframes.html' --w 1328 --h 640 --out "$PREVIEW_ROOT/keyframes.png"
```

检查 `keyframes.png` 确实包含六张画面及时间标签，且未裁掉第二行。需要竖版时，另运行取帧命令，改为 `--orient portrait --w 360 --h 640`，输出到 `key-portrait.png`；拼条中的图片路径和 `aspect-ratio` 相应改为竖版，并调整截图高度后检查整条画面。
横竖两版要来自各自构图。

## 关键片段：2–3 秒

围绕最能区分方向的一次转场或能量峰值截取 2–3 秒。`render.mjs` 支持 `--from`／`--to`（秒）；下例取 `21–23s`，12fps、640×360、JPEG，共 24 帧；有 ffmpeg 时合成 `clip-landscape.mp4`：

```bash
node "$MOTION_ROOT/scripts/render.mjs" 'http://127.0.0.1:4331/demo/demos/cases/map-pilgrimage/index.html' --orient landscape --w 640 --h 360 --fps 12 --from 21 --to 23 --format jpeg --out "$PREVIEW_ROOT/clip-landscape"
node "$MOTION_ROOT/scripts/render.mjs" 'http://127.0.0.1:4331/demo/demos/cases/map-pilgrimage/index.html' --orient portrait --w 360 --h 640 --fps 12 --from 21 --to 23 --format jpeg --out "$PREVIEW_ROOT/clip-portrait"
```

只需一个画幅时只运行对应命令。工具自动设置 `render=1`、`embed=1`、`orient`，等待 `ready`，逐帧 seek；`--no-encode` 只保留帧序列。没有 ffmpeg 时，按脚本打印的命令合成后再展示关键片段。
需要听声音时加 `--audio`；只有挂乐谱的 `__motion.audio` 能离线渲染同一区间 WAV，并随 MP4 封装。`--audio-only` 只输出 WAV；`--sample-rate` 默认为 48000。未挂乐谱时脚本跳过声音。

渲染器的编码失败不一定让进程返回非零，必须确认 MP4 实际存在并读取其参数：

```bash
ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=width,height,r_frame_rate,nb_read_frames:format=duration -of json "$PREVIEW_ROOT/clip-landscape.mp4"
```

横版结果应为 `640×360`、`12/1`、`24` 帧、`2.000000` 秒；再目视片段首尾或实际播放。此片段覆盖展开和全屏停留，不覆盖约 `24.35s` 的回程完成；验收回程时另截该时刻。

## 资源与完成状态

`map-pilgrimage` 依赖外部 MapLibre、OpenFreeMap 与地形瓦片；默认卡片画面由 `scenes.js` 生成。地图不可用时 Demo 会退回纸面网格，预加载失败或瓦片等待超时后 `ready`／`seek` 也可能完成。取帧后目视地图与主要元素已经加载；地图缺失时 `#stage` 含 `no-map`，修复网络或路径后重跑受影响的步骤。

截图工具对 `ready` 的等待为 60 秒，Demo 的预加载上限为 120 秒。慢网导致前者超时时，先检查资源；需要更长等待时在用户项目的无头浏览器中等待 `ready`，再 `await seek(t)` 截图，保留实际等待和未就绪状态，不改只读上游脚本。

## 选定方向后正式渲染

确认用户方向后，才正式渲染完整片段。移除 `--from`／`--to`，默认覆盖 `0–duration`；横屏默认 1920×1080，竖屏默认 1080×1920，默认 30fps。例如：

```bash
node "$MOTION_ROOT/scripts/render.mjs" 'http://127.0.0.1:4331/demo/demos/cases/map-pilgrimage/index.html' --orient landscape --fps 30 --audio --out "$PREVIEW_ROOT/final-landscape"
```

对照最终节拍表检查时长、关键帧与声音同步；交互作品另在真实输入和外部 seek／play 之间切换验证。输出帧、第三方素材和参考视频取帧只留在工作区，不纳入 Git 提交。
