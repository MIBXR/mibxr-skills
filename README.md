# My Skills

个人可复用的 Codex 技能。这里保存通用方法与小型核验工具，具体作品、图片和角色设定保存在各自作品仓库。两个技能均支持自动识别，也可显式调用。

| 技能 | 用途 |
| --- | --- |
| [desktop-pet-workflow](skills/desktop-pet-workflow/SKILL.md) | 桌宠制作、局部修复、正式图集验证和便携交付 |
| [static-site-delivery](skills/static-site-delivery/SKILL.md) | 展示网站源码整理、下载对应关系、远端发布及恢复 |

## 换电脑安装

这是私有仓库。先在新环境登录有访问权限的 GitHub 账号，并配置 Git 使用该身份；不要把令牌写入仓库或聊天。

```sh
gh auth login --hostname github.com
gh auth setup-git --hostname github.com
```

在 Codex 中使用内置 `$skill-installer`，发送：

```text
请从 MIBXR/my-skills 的 v1.0.0 标签安装
skills/desktop-pet-workflow 和 skills/static-site-delivery。
这是私有仓库，请使用当前已授权的 GitHub 身份。
```

也可调用当前安装版本的官方 `install-skill-from-github.py`，传入：

```text
--repo MIBXR/my-skills --ref v1.0.0 --path skills/desktop-pet-workflow skills/static-site-delivery --method git
```

脚本位置由当前 Codex 安装提供，先定位内置 skill-installer，不写死电脑路径。默认安装目录由 `CODEX_HOME` 决定；要试装到隔离目录可使用 `--dest`。已有同名技能时先比较和备份，再明确选择升级方式。

安装完成后重新打开 Codex 或按当前安装器提示刷新技能列表。可发送：

```text
$desktop-pet-workflow 检查这组动画，修复挥手时的身体抖动，保留其他动作。
$static-site-delivery 把这个展示网站整理为可以在新电脑恢复的源码。
```

## 依赖和边界

阅读技能不需要额外依赖。可选图集比较脚本需要 Python 3.10+ 和 Pillow；通过 `python -m pip install -r requirements-tools.txt` 安装。制作、修图、应用导入或网站发布使用目标环境现有工具及认证，技能不会自动安装插件或迁移登录态。

技能不包含本机绝对路径、账号实例、临时凭据、缓存或作品素材。参考来源见 [来源与维护](docs/maintenance.md)。

## 验证和升级

```sh
python -m pip install -r requirements-tools.txt
python -m unittest discover -s tests
```

修改技能后，使用当前内置 skill-creator 的 `quick_validate.py` 分别验证两个文件夹，并检查真实任务中的决策。发布新标签后在新环境按该标签安装。测试工具仅验证像素保留等确定性条件，不能证明画面质量或目标应用已正常播放。
