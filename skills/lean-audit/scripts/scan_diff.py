#!/usr/bin/env python3
"""扫描一段改动中超出计划的内容，输出 JSON：flags 可直接判定，review 需逐句判断。

不给 --range 时扫描工作区相对 HEAD 的改动（含未跟踪文件）。
"""
import argparse
import json
import re
import sys
import subprocess
from collections import Counter
from pathlib import Path

CODE_RULES = [
    ("hash", re.compile(r"sha256|sha1|md5|createHash|hashlib|checksum|digest|integrity", re.I)),
    ("try/catch", re.compile(r"\bcatch\s*[({]|except\s+Exception|except\s*:")),
]
PROSE_WORDS = re.compile(
    r"不要|不能|不是|不会|尚未|仍|可能|为准|现名|旧|另行|避免|确认|只是|不代表|不保证|仅供|请勿|注意|"
    r"之前|原来|曾经|改名|以前|暂时|目前|兼容|风险|哈希|"
    r"\b(note that|please note|keep in mind|be aware|does not (guarantee|mean|imply)|not guaranteed|"
    r"for reference only|previously|formerly|renamed|no longer|caveat|disclaimer)\b",
    re.I,
)
TEST_NAME = re.compile(r"(^|[/._-])(tests?|specs?|__tests__|smoke|checks?|verify|fixtures?)([/._-]|$)", re.I)
PROSE_FILE = re.compile(r"\.(md|mdx|html?|txt|rst)$", re.I)
IDENT = re.compile(r"`([^`\s]{3,})`")


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


def scan(repo, rng=None, files=(), verbatim=()):
    if git(repo, "rev-parse", "--is-inside-work-tree").strip() != "true":
        raise SystemExit(f"不是 Git 仓库：{repo}")
    flags, review, idents = [], [], Counter()
    for f, lines in changed_lines(repo, rng).items():
        if files and not under(f, files):
            flags.append(f"计划外的文件：{f}")
        if TEST_NAME.search(f):
            flags.append(f"测试或检查文件：{f}")
        if under(f, verbatim):
            continue
        for name, rule in CODE_RULES:
            hits = [l.strip()[:80] for l in lines if rule.search(l)]
            if hits:
                flags.append(f"{name}：{f}（{len(hits)} 处）" + " | ".join(hits[:3]))
        if not PROSE_FILE.search(f):
            continue
        fence = False
        for l in lines:
            if l.lstrip().startswith("```"):
                fence = not fence
                continue
            if fence or l.lstrip().startswith("|") or not l.strip():
                continue
            if PROSE_WORDS.search(l):
                review.append(f"{f}: {l.strip()[:160]}")
            idents.update(IDENT.findall(l))
    review += [f"正文重复出现 {n} 次：`{k}`" for k, n in idents.items() if n >= 3]
    return {"flags": flags, "review": review}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=".", help="仓库路径")
    ap.add_argument("--range", help="提交区间，如 main..HEAD；省略时扫描工作区")
    ap.add_argument("--files", default="", help="计划允许改动的路径，逗号分隔，目录以 / 结尾")
    ap.add_argument("--verbatim", default="", help="原样复制进来的路径，内容不扫描")
    a = ap.parse_args()
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]
    print(json.dumps(scan(a.repo, a.range, split(a.files), split(a.verbatim)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
