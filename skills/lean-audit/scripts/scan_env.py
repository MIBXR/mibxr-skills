#!/usr/bin/env python3
"""找出当前电脑上各 Agent 的全局指令、配置、记忆与技能，标出可能诱发过度设计的行，输出 JSON。"""
import argparse
import json
import re
import sys
from pathlib import Path

HOME = Path.home()
INSTRUCTIONS = [
    ("codex", HOME / ".codex/AGENTS.md"),
    ("codex", HOME / ".codex/config.toml"),
    ("claude", HOME / ".claude/CLAUDE.md"),
    ("claude", HOME / ".claude/settings.json"),
    ("gemini", HOME / ".gemini/GEMINI.md"),
]
MEMORY_DIRS = [("codex", HOME / ".codex/memories")]
SKILL_DIRS = [("codex", HOME / ".codex/skills"), ("claude", HOME / ".claude/skills"), ("shared", HOME / ".agents/skills")]
AGENT_DIRS = [("claude", HOME / ".claude/agents")]
PROJECT_FILES = ["AGENTS.md", "CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md"]
PROJECT_GLOBS = [".cursor/rules/**/*", ".claude/skills/*/SKILL.md", ".agents/skills/*/SKILL.md", ".claude/agents/*.md"]

PATTERNS = {
    "汇报与免责": r"已验证|未验证|推断|遗留问题|限制|风险|不代表|不保证|caveat|limitation|unverified|risks?\b",
    "核对与哈希": r"哈希|hash|sha256|checksum|逐字节|byte-for-byte|核对|校验|回读|read back|verif(y|ication)",
    "测试": r"测试|回归|冒烟|test suite|regression|smoke|\btdd\b|red-green|failing test",
    "写入仓库": r"写入仓库|提交到仓库|in the repo|GLOSSARY|ADR|docs/adr|research notes|调研",
    "穷尽": r"不计成本|refuse to give up|disproportionate|exhaustive|every edge case|完整测试|full test suite|全部检查",
}
RULES = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}
BLOCK = re.compile(r"<!-- lean-audit:begin -->.*?<!-- lean-audit:end -->", re.S)
MAX_HITS = 30


def hits(path):
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # 本技能写入的规则块不算诱因
    text = BLOCK.sub(lambda m: "\n" * m.group(0).count("\n"), raw)
    found = []
    for i, line in enumerate(text.splitlines(), 1):
        cats = [k for k, r in RULES.items() if r.search(line)]
        if cats:
            found.append({"line": i, "kind": cats, "text": line.strip()[:160]})
    return {"path": str(path), "has_lean_audit_block": "lean-audit:begin" in raw,
            "hit_count": len(found), "hits": found[:MAX_HITS]}


def implicit(skill_dir):
    """技能是否允许模型自动调用。"""
    md = skill_dir / "SKILL.md"
    head = md.read_text(encoding="utf-8", errors="replace").split("---", 2)[1] if md.exists() else ""
    if re.search(r"disable-model-invocation:\s*true", head):
        return False
    yaml = skill_dir / "agents/openai.yaml"
    if yaml.exists() and re.search(r"allow_implicit_invocation:\s*false", yaml.read_text(encoding="utf-8", errors="replace")):
        return False
    return True


def skill_entry(agent, skill_dir):
    files = [p for p in skill_dir.rglob("*.md") if p.is_file()]
    found = [h for h in (hits(p) for p in files) if h and h["hit_count"]]
    return {"agent": agent, "skill": skill_dir.name, "auto_invoked": implicit(skill_dir),
            "hit_count": sum(h["hit_count"] for h in found),
            "kinds": sorted({k for h in found for x in h["hits"] for k in x["kind"]}),
            "sample": [f"{Path(h['path']).name}:{x['line']}: {x['text']}" for h in found for x in h["hits"]][:6]}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", help="同时扫描这个项目目录里的指令与技能")
    a = ap.parse_args()

    out = {"instructions": [], "memories": [], "agents": [], "skills": []}
    for agent, p in INSTRUCTIONS:
        if p.is_file():
            out["instructions"].append({"agent": agent, **hits(p)})
    for agent, d in MEMORY_DIRS:
        for p in sorted(d.glob("*.md")) if d.is_dir() else []:
            h = hits(p)
            if h and h["hit_count"]:
                out["memories"].append({"agent": agent, **h})
    for agent, d in AGENT_DIRS:
        for p in sorted(d.glob("*.md")) if d.is_dir() else []:
            out["agents"].append({"agent": agent, **hits(p)})
    for agent, d in SKILL_DIRS:
        for s in sorted(d.iterdir()) if d.is_dir() else []:
            if (s / "SKILL.md").is_file():
                out["skills"].append(skill_entry(agent, s))

    if a.project:
        root = Path(a.project)
        paths = [root / f for f in PROJECT_FILES] + [p for g in PROJECT_GLOBS for p in root.glob(g)]
        out["project"] = [{"agent": "project", **hits(p)} for p in paths if p.is_file()]

    out["skills"].sort(key=lambda s: (not s["auto_invoked"], -s["hit_count"]))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
