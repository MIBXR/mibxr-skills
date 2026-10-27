#!/usr/bin/env python3
"""扫描一段改动中超出计划的内容，输出 JSON：flags 可直接判定，review 需逐句判断。

不给 --range 时扫描工作区相对 HEAD 的改动（含未跟踪文件）。
原样收录的内容自动跳过：.gitattributes 中标为 linguist-vendored / linguist-generated 的路径、
常见的第三方与构建目录、压缩文件、锁文件与许可证文本；其余用 --verbatim 指定。
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

CODE_FILE = re.compile(r"\.(m?js|cjs|jsx|tsx?|py|go|rs|rb|java|kt|swift|sh|ps1)$", re.I)
DOC_FILE = re.compile(r"\.(md|mdx|rst|txt)$", re.I)
PROSE_FILE = re.compile(r"\.(md|mdx|rst)$", re.I)
SKIP_PATH = re.compile(
    r"(^|/)(vendor|vendored|third[_-]?party|node_modules|dist|build|\.next|coverage)/"
    r"|\.min\.(js|css)$|(^|/)assets/index-[\w-]+\.(js|css)$"
    r"|(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|Cargo\.lock)$"
    r"|(^|/)(LICENSE|LICENCE|COPYING|NOTICE)[^/]*$|(^|/)[^/]*-?OFL[^/]*\.txt$",
    re.I,
)
TEST_FILE = re.compile(
    r"(^|/)(tests?|__tests__|spec|e2e)/|\.(test|spec)\.[cm]?[jt]sx?$|(^|/)test_[^/]+\.py$|_test\.(py|go)$",
    re.I,
)
CHECK_SCRIPT = re.compile(r"(^|/)(check|verify|smoke|validate)([-_.][^/]*)?\.(m?js|cjs|ts|py|sh|ps1)$", re.I)
HASH = re.compile(r"createHash|hashlib|\bsha(1|256|512)\b|\bmd5\b|checksum", re.I)
SWALLOW = re.compile(
    r"catch\s*(\([^)]*\))?\s*\{\s*(/\*.*?\*/\s*|//[^\n]*)?(return\s*(null|false|undefined|\[\]|\{\}|''|\"\")?\s*;?\s*)?\}"
    r"|\.catch\(\s*\(\s*\w*\s*\)\s*=>\s*(\{\s*\}|null|undefined|false)\s*\)"
    r"|except(\s+\w+(\s+as\s+\w+)?)?\s*:\s*(pass|return(\s+None)?|continue)\s*$"
)
# 强信号：免责、验证状态、过程与改名
STRONG = re.compile(
    r"不代表|不意味着|不自动(表示|等于|说明)|不保证|仅供参考|请勿|注意[：:]|"
    r"未验证|未实测|未经(验证|确认)|尚未.{0,6}(验证|确认|实测|核实)|仍需.{0,4}(确认|验证)|仍未|"
    r"以[^，。；]{1,16}为准|不作[^，。；]{0,8}(认证|保证)|不能(据此|单独|证明|替代)|只能说明|仍只是|"
    r"之前|原来|曾经|以前|改名|现名|更名|"
    r"\b(not (yet )?verified|unverified|does not (guarantee|mean|imply)|not guaranteed|for reference only|"
    r"previously|formerly|renamed|no longer)\b",
    re.I,
)
# 弱信号：只在说明文档里看
WEAK = re.compile(r"不要|不能|不是|不会|尚未|可能|另行|避免|只是|\b(note that|keep in mind|be aware)\b", re.I)
IDENT = re.compile(r"`([A-Za-z][\w-]{2,})`")
MINIFIED = 400


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def under(path, prefixes):
    return any(path == p or path.startswith(p if p.endswith("/") else p + "/") for p in prefixes)


def changed_lines(repo, rng):
    changed, cur = {}, None
    for line in git(repo, "diff", "-U0", rng or "HEAD").splitlines():
        if line.startswith("+++ "):
            cur = None if line[4:] == "/dev/null" else re.sub(r"^b/", "", line[4:])
            if cur:
                changed[cur] = []
        elif cur and line.startswith("+"):
            changed[cur].append(line[1:])
    if not rng:
        for f in filter(None, git(repo, "ls-files", "--others", "--exclude-standard").splitlines()):
            p = Path(repo, f)
            if p.is_file() and p.stat().st_size < 2_000_000:
                changed[f] = p.read_text(encoding="utf-8", errors="replace").splitlines()
    return changed


def attr_skipped(repo, files):
    """.gitattributes 标为 linguist-vendored / linguist-generated 的文件。"""
    if not files:
        return set()
    out = subprocess.run(["git", "-C", repo, "check-attr", "--stdin", "linguist-vendored", "linguist-generated"],
                         input="\n".join(files), capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    return {l.split(": ")[0] for l in out.splitlines() if l.endswith(": set") or l.endswith(": true")}


def is_doc(path):
    name = path.rsplit("/", 1)[-1]
    return DOC_FILE.search(path) and (path.count("/") == 0 or re.match(r"(docs?|guides?)/", path) or name.upper().startswith(("README", "CONTRIBUTING", "AGENT")))


def scan(repo, rng=None, files=(), verbatim=(), limit=80):
    if git(repo, "rev-parse", "--is-inside-work-tree").strip() != "true":
        raise SystemExit(f"不是 Git 仓库：{repo}")
    changed = changed_lines(repo, rng)
    skipped = attr_skipped(repo, list(changed)) | {f for f in changed if SKIP_PATH.search(f) or under(f, verbatim)}
    flags, strong, weak = [], [], []
    idents = defaultdict(Counter)  # 说明文档正文里每个名称在各文件出现的次数
    for f, lines in changed.items():
        if files and not under(f, files):
            flags.append(f"计划外的文件：{f}")
        if f in skipped:
            continue
        if TEST_FILE.search(f):
            flags.append(f"测试文件：{f}")
        elif CHECK_SCRIPT.search(f):
            flags.append(f"检查脚本：{f}")
        lines = [l for l in lines if len(l) <= MINIFIED]  # 超长行多为压缩或内联数据
        if CODE_FILE.search(f):
            for name, rule in (("哈希", HASH), ("静默吞错", SWALLOW)):
                hits = [l.strip()[:80] for l in lines if rule.search(l)]
                if hits:
                    flags.append(f"{name}：{f}（{len(hits)} 处）" + " | ".join(hits[:2]))
        doc = is_doc(f)
        if not (doc or PROSE_FILE.search(f)):
            continue
        fence = False
        for l in lines:
            if l.lstrip().startswith("```"):
                fence = not fence
                continue
            if fence or l.lstrip().startswith("|") or not l.strip():
                continue
            if STRONG.search(l):
                strong.append(f"{f}: {l.strip()[:160]}")
            elif doc and WEAK.search(l):
                weak.append(f"{f}: {l.strip()[:160]}")
            if doc:
                for k in IDENT.findall(l):
                    idents[k][f] += 1

    for k, per in idents.items():
        if sum(per.values()) >= 4:
            where = "、".join(f"{f}×{n}" for f, n in per.most_common())
            strong.append(f"正文重复 {sum(per.values())} 次 `{k}`: {where}")
    review = strong + weak
    per_file = defaultdict(int)
    for x in review:
        per_file[x.split(": ", 1)[0]] += 1
    return {
        "summary": {"files": len(changed), "skipped": len(skipped), "flags": len(flags),
                    "review": len(review), "review_strong": len(strong),
                    "top_files": sorted(per_file.items(), key=lambda kv: -kv[1])[:10]},
        "flags": flags,
        "review": review[:limit],
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".", help="仓库路径")
    ap.add_argument("--range", help="提交区间，如 main..HEAD；省略时扫描工作区")
    ap.add_argument("--files", default="", help="计划允许改动的路径，逗号分隔，目录以 / 结尾")
    ap.add_argument("--verbatim", default="", help="原样收录的路径，内容不扫描")
    ap.add_argument("--limit", type=int, default=80, help="review 最多输出的条数（强信号在前）")
    a = ap.parse_args()
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]
    print(json.dumps(scan(a.repo, a.range, split(a.files), split(a.verbatim), a.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
