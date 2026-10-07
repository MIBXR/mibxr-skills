#!/usr/bin/env python3
"""Retrieve Design Atlas references without a website UI or third-party packages."""

import argparse
import hashlib
import json
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

SKILL_ROOT = Path(__file__).resolve().parent.parent
HASH = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
ROLES = {"source", "asset", "context", "preview"}


class AtlasError(Exception):
    pass


def path_parts(value):
    if not isinstance(value, str) or not value or re.search(r'[\\\x00<>:"|?*]', value):
        raise AtlasError(f"Invalid repository path: {value!r}")
    parts = value.split("/")
    if PurePosixPath(value).is_absolute() or any(p in ("", ".", "..") for p in parts):
        raise AtlasError(f"Unsafe repository path: {value!r}")
    if any(any(ord(c) < 32 for c in p) for p in parts):
        raise AtlasError(f"Invalid repository path: {value!r}")
    if any(re.search(r'[. ]$', p) or re.match(r'^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', p, re.I) for p in parts):
        raise AtlasError(f"Non-portable repository path: {value!r}")
    return parts


def no_symlinks(path):
    for component in [path, *path.parents]:
        if component.is_symlink() or (hasattr(component, 'is_junction') and component.is_junction()):
            raise AtlasError(f"Symbolic links and directory junctions are not supported: {component}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_data(data, record):
    expected = record.get("sha256")
    count = record.get("bytes")
    if not isinstance(expected, str) or not HASH.fullmatch(expected):
        raise AtlasError(f"Missing SHA-256 for {record.get('path', 'resource')}")
    if not isinstance(count, int) or count < 0 or len(data) != count:
        raise AtlasError(f"Byte length mismatch: {record.get('path', 'resource')}")
    if digest(data) != expected:
        raise AtlasError(f"SHA-256 mismatch: {record.get('path', 'resource')}")


def parse_json(data, name):
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise AtlasError(f"Invalid UTF-8 JSON at {name}: {exc}") from exc


class Atlas:
    def __init__(self, args):
        lock = parse_json((SKILL_ROOT / "upstream.lock.json").read_bytes(), "upstream.lock.json")
        self.repository = lock["repository"]
        self.ref = args.ref or lock["ref"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository):
            raise AtlasError("Invalid repository in upstream.lock.json")
        if not COMMIT.fullmatch(self.ref):
            raise AtlasError("--ref and upstream.lock.json must use a full 40-character Git commit")
        self.local = Path(args.local_root).absolute() if args.local_root else None
        if self.local:
            no_symlinks(self.local)
            if not self.local.is_dir():
                raise AtlasError(f"Local checkout does not exist: {self.local}")
        self.base = f"https://raw.githubusercontent.com/{self.repository}/{self.ref}/"
        self.catalog = parse_json(self.read(lock["catalog"]), lock["catalog"])
        if self.catalog.get("schemaVersion") != lock["schemaVersion"]:
            raise AtlasError("Catalog schemaVersion is incompatible with this skill")
        entries = self.catalog.get("entries")
        if not isinstance(entries, list) or self.catalog.get("entryCount") != len(entries):
            raise AtlasError("Catalog entries or entryCount are invalid")
        if not HASH.fullmatch(str(self.catalog.get("contentVersion", ""))):
            raise AtlasError("Catalog contentVersion must be a SHA-256 digest")
        if self.catalog.get("repository") not in {self.repository, f"https://github.com/{self.repository}"}:
            raise AtlasError("Catalog repository differs from upstream.lock.json")
        self.entries = {}
        for entry in entries:
            case_id = entry.get("id")
            if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", case_id):
                raise AtlasError("Catalog contains an invalid case ID")
            if case_id in self.entries:
                raise AtlasError(f"Duplicate case ID: {case_id}")
            path_parts(entry.get("paths", {}).get("bundle"))
            if not HASH.fullmatch(str(entry.get("bundleSha256", ""))):
                raise AtlasError(f"Invalid bundleSha256: {case_id}")
            self.entries[case_id] = entry
        version = ''.join(f"{case_id}:{self.entries[case_id]['bundleSha256']}\n" for case_id in sorted(self.entries))
        if digest(version.encode('utf-8')) != self.catalog['contentVersion']:
            raise AtlasError('Catalog contentVersion differs from its case hashes')

    def url(self, path):
        path_parts(path)
        return self.base + urllib.parse.quote(path, safe="/")

    def read(self, path):
        parts = path_parts(path)
        if self.local:
            target = self.local.joinpath(*parts)
            no_symlinks(target)
            try:
                return target.read_bytes()
            except OSError as exc:
                raise AtlasError(f"Cannot read local file {path}: {exc}") from exc
        request = urllib.request.Request(self.url(path), headers={"User-Agent": "mibxr-design-atlas-skill/1"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (OSError, urllib.error.URLError) as exc:
            raise AtlasError(f"Cannot retrieve {path} at {self.ref}: {exc}") from exc

    def provenance(self):
        return {
            "repository": self.repository,
            "ref": self.ref if self.local is None else None,
            "localRoot": str(self.local) if self.local else None,
            "contentVersion": self.catalog["contentVersion"],
            "schemaVersion": self.catalog["schemaVersion"],
        }

    def bundle(self, case_id):
        if case_id not in self.entries:
            raise AtlasError(f"Unknown case ID: {case_id}")
        entry = self.entries[case_id]
        data = self.read(entry["paths"]["bundle"])
        if digest(data) != entry["bundleSha256"]:
            raise AtlasError(f"Bundle SHA-256 mismatch: {case_id}")
        bundle = parse_json(data, entry["paths"]["bundle"])
        if bundle.get("schemaVersion") != self.catalog["schemaVersion"] or bundle.get("id") != case_id:
            raise AtlasError(f"Bundle identity or schemaVersion mismatch: {case_id}")
        if bundle.get("entry", {}).get("id") != case_id:
            raise AtlasError(f"Bundle entry identity mismatch: {case_id}")
        documents = bundle.get("documents")
        files = bundle.get("files")
        if not isinstance(documents, list) or not isinstance(files, list):
            raise AtlasError(f"Bundle documents/files are invalid: {case_id}")
        seen = set()
        for record in files:
            path_parts(record.get("path"))
            key = record["path"].casefold()
            if key in seen or record["role"] not in ROLES:
                raise AtlasError(f"Duplicate file path or invalid role: {record['path']}")
            seen.add(key)
            if not HASH.fullmatch(str(record.get("sha256", ""))) or not isinstance(record.get("bytes"), int):
                raise AtlasError(f"Invalid file integrity metadata: {record['path']}")
        for document in documents:
            path_parts(document.get("path"))
            if not isinstance(document.get("content"), str):
                raise AtlasError(f"Document has no full text: {document.get('path')}")
            verify_data(document["content"].encode("utf-8"), document)
        return bundle


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def search(atlas, args):
    terms = list(dict.fromkeys(t.casefold() for t in re.split(r'[\s,，;；]+', args.query) if t))
    fields = ['id', 'title', 'tags', 'category', 'useCases', 'summary', 'tokens', 'composition', 'interaction', 'themeBehavior', 'soundBehavior', 'avoid']
    results = []
    for entry in atlas.entries.values():
        if args.category and entry.get("category", "").casefold() != args.category.casefold():
            continue
        haystacks = {field: json.dumps(entry.get(field, ''), ensure_ascii=False).casefold() for field in fields}
        matches = [{"term": term, "fields": [field for field in fields if term in haystacks[field]]} for term in terms]
        matches = [match for match in matches if match['fields']]
        if terms and not matches:
            continue
        score = sum(4 if field in {'id', 'title', 'tags', 'useCases'} else 1 if field == 'avoid' else 2 for match in matches for field in match['fields'])
        summary = {k: entry.get(k) for k in ["id", "title", "category", "tags", "summary", "useCases", "avoid", "paths"]}
        summary["score"] = score
        summary["matches"] = matches
        results.append(summary)
    results.sort(key=lambda row: (-row["score"], row["id"]))
    emit({"schemaVersion": 1, "contentVersion": atlas.catalog['contentVersion'], "provenance": atlas.provenance(), "query": args.query, "method": "keyword", "total": len(results), "results": results[:args.limit]})


def show(atlas, args):
    bundle = atlas.bundle(args.case_id)
    result = {**bundle, "provenance": atlas.provenance()}
    if args.source:
        sources = []
        for record in bundle["files"]:
            if record["role"] == "source":
                data = atlas.read(record["path"])
                verify_data(data, record)
                try:
                    content = data.decode("utf-8")
                except UnicodeError as exc:
                    raise AtlasError(f"Source is not UTF-8: {record['path']}") from exc
                sources.append({**record, "content": content})
        result["source"] = sources
    emit(result)


def export(atlas, args):
    bundle = atlas.bundle(args.case_id)
    out = Path(args.out).absolute()
    no_symlinks(out)
    if out.exists():
        raise AtlasError(f"Export requires a new directory; already exists: {out}")
    selected = [r for r in bundle["files"] if not args.code_only or r["role"] in {"source", "context"}]
    if any(r["path"].casefold() == "atlas-export.json" for r in selected):
        raise AtlasError("Source manifest conflicts with export metadata")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir()
    try:
        for record in selected:
            data = atlas.read(record["path"])
            verify_data(data, record)
            target = out.joinpath(*path_parts(record["path"]))
            no_symlinks(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(data)
        metadata = {
            "schemaVersion": 1, "id": args.case_id, "provenance": atlas.provenance(),
            "paths": atlas.entries[args.case_id]["paths"],
            "codeOnly": args.code_only, "files": selected,
            "omitted": [r["path"] for r in bundle["files"] if r not in selected],
            "filesNotDownloaded": [{**r, "url": atlas.url(r["path"]) if not atlas.local else None} for r in bundle["files"] if r not in selected],
            "bundle": bundle,
        }
        with (out / "atlas-export.json").open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except Exception:
        shutil.rmtree(out)
        raise
    emit({"id": args.case_id, "provenance": atlas.provenance(), "directory": str(out), "files": len(selected), "bytes": sum(r['bytes'] for r in selected), "omitted": metadata['omitted'], "entrypoint": metadata["paths"]["demo"]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-root", help="Read a local Design Atlas checkout without network access")
    parser.add_argument("--ref", help="Override the lock with an explicit full 40-character Git commit")
    commands = parser.add_subparsers(dest="command", required=True)
    find = commands.add_parser("search", help="Search case metadata by keywords")
    find.add_argument("query", nargs="?", default="")
    find.add_argument("--category", help="Exact category filter")
    find.add_argument("--limit", type=int, default=5)
    detail = commands.add_parser("show", help="Read the full case bundle and optionally full source")
    detail.add_argument("case_id")
    detail.add_argument("--source", action="store_true")
    save = commands.add_parser("export", help="Download and hash-verify a case into a new directory")
    save.add_argument("case_id")
    save.add_argument("--out", required=True)
    save.add_argument("--code-only", action="store_true", help="Download source/context and explicitly list omitted media")
    info = commands.add_parser("info", help="Verify the catalog and report the active upstream version")
    args = parser.parse_args()
    if hasattr(args, "limit") and not 1 <= args.limit <= 100:
        parser.error("--limit must be from 1 to 100")
    try:
        atlas = Atlas(args)
        if args.command == "search":
            search(atlas, args)
        elif args.command == "show":
            show(atlas, args)
        elif args.command == "export":
            export(atlas, args)
        else:
            emit({"provenance": atlas.provenance(), "entryCount": len(atlas.entries)})
        return 0
    except (AtlasError, OSError, KeyError, TypeError) as exc:
        print(f"design-atlas: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
