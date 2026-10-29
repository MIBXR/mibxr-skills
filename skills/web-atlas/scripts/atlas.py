#!/usr/bin/env python3
"""Retrieve Web Atlas references without a website UI or third-party packages."""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone

SKILL_ROOT = Path(__file__).resolve().parent.parent
COMMIT = re.compile(r"^[0-9a-f]{40}$")
EXPERIENCE_TYPES = ('visual', 'micro-motion', 'page-motion', 'sound', 'structure')


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


def parse_json(data, name):
    try:
        value = json.loads(data.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise AtlasError(f"Invalid UTF-8 JSON at {name}: {exc}") from exc
    if not isinstance(value, dict):
        raise AtlasError(f'Expected a JSON object at {name}')
    return value


class Atlas:
    def __init__(self, args):
        lock = parse_json((SKILL_ROOT / "upstream.lock.json").read_bytes(), "upstream.lock.json")
        self.repository = lock["repository"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository):
            raise AtlasError("Invalid repository in upstream.lock.json")
        explicit_ref = args.ref
        if explicit_ref and not COMMIT.fullmatch(explicit_ref):
            raise AtlasError("--ref must use a full 40-character Git commit")
        self.session = Path(args.session).absolute() if args.session else None
        self.previous_ref = None
        self.default_branch = None
        saved_session = None
        if self.session:
            no_symlinks(self.session)
            self.session = self.session.resolve()
            if self.session == SKILL_ROOT or SKILL_ROOT in self.session.parents:
                raise AtlasError("Save --session in the user's working directory, outside the installed skill")
            if self.session.exists():
                saved_session = parse_json(self.session.read_bytes(), str(self.session))
                if saved_session.get('sessionVersion') != 1 or saved_session.get('repository') != self.repository or saved_session.get('schemaVersion') != lock['schemaVersion']:
                    raise AtlasError('Session repository or schema is incompatible; use a separate session file')
                if not COMMIT.fullmatch(str(saved_session.get('ref', ''))):
                    raise AtlasError('Session ref is invalid')
                self.previous_ref = saved_session['ref']
                self.default_branch = saved_session.get('defaultBranch')
        self.local = Path(args.local_root).absolute() if args.local_root else None
        if self.local:
            no_symlinks(self.local)
            if not self.local.is_dir():
                raise AtlasError(f"Local checkout does not exist: {self.local}")
            self.ref = None
            self.resolution = 'local'
        elif saved_session and args.command != 'refresh':
            if explicit_ref and explicit_ref != saved_session['ref']:
                raise AtlasError('--ref differs from this session; use a separate session file')
            self.ref = saved_session['ref']
            self.resolution = 'session'
        elif explicit_ref:
            self.ref = explicit_ref
            self.resolution = 'explicit-ref'
        else:
            self.ref, self.default_branch = self.resolve_latest()
            self.resolution = 'latest-default-branch'
        self.base = f"https://raw.githubusercontent.com/{self.repository}/{self.ref}/"
        self.catalog = parse_json(self.read(lock["catalog"]), lock["catalog"])
        self.entries = {entry['id']: entry for entry in self.catalog['entries']}
        self.patterns = None
        self.materials = None
        if args.command.startswith('pattern-'):
            self.require_patterns()
        if args.command.startswith('material-'):
            self.require_materials()
        if self.session and (saved_session is None or args.command == 'refresh'):
            self.write_session(replace=saved_session is not None)

    def resolve_latest(self):
        api = f'https://api.github.com/repos/{self.repository}'
        def request_json(url):
            request = urllib.request.Request(url, headers={'User-Agent': 'mibxr-web-atlas-skill/1', 'Accept': 'application/vnd.github+json'})
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return parse_json(response.read(), url)
            except (OSError, urllib.error.URLError) as exc:
                raise AtlasError(f'Cannot resolve the latest default-branch commit: {exc}. Use an existing --session, an explicit --ref, or --local-root.') from exc
        repository = request_json(api)
        branch = repository.get('default_branch')
        if not isinstance(branch, str) or not branch:
            raise AtlasError('GitHub did not return a default branch')
        commit = request_json(api + '/commits/' + urllib.parse.quote(branch, safe=''))
        ref = commit.get('sha')
        if not isinstance(ref, str) or not COMMIT.fullmatch(ref):
            raise AtlasError('GitHub did not return a full commit SHA for the default branch')
        return ref, branch

    def write_session(self, replace):
        state = {
            'sessionVersion': 1, 'repository': self.repository, 'ref': self.ref,
            'defaultBranch': self.default_branch, 'schemaVersion': self.catalog['schemaVersion'],
            'resolvedAt': datetime.now(timezone.utc).isoformat(),
        }
        no_symlinks(self.session)
        self.session.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.atlas-session-', suffix='.tmp', dir=self.session.parent)
        temporary = Path(temporary)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            no_symlinks(self.session)
            if replace:
                os.replace(temporary, self.session)
            else:
                try:
                    os.link(temporary, self.session)
                except FileExistsError as exc:
                    raise AtlasError('Another command created this session; rerun to use its pinned version') from exc
        finally:
            temporary.unlink(missing_ok=True)

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
        request = urllib.request.Request(self.url(path), headers={"User-Agent": "mibxr-web-atlas-skill/1"})
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
            "schemaVersion": self.catalog["schemaVersion"],
            "resolution": self.resolution,
            "defaultBranch": self.default_branch,
            "session": str(self.session) if self.session else None,
        }

    def bundle(self, case_id):
        if case_id not in self.entries:
            raise AtlasError(f"Unknown case ID: {case_id}")
        path = self.entries[case_id]['paths']['bundle']
        return parse_json(self.read(path), path)

    def require_materials(self):
        if self.materials is None:
            manifest = self.catalog['materials']
            catalog = parse_json(self.read(manifest['path']), manifest['path'])
            self.materials = {row['id']: row for row in catalog['materials']}

    def material_bundle(self, material_id):
        self.require_materials()
        if material_id not in self.materials:
            raise AtlasError(f'Unknown material ID: {material_id}')
        path = self.materials[material_id]['paths']['bundle']
        return parse_json(self.read(path), path)

    def require_patterns(self):
        if self.patterns is None:
            manifest = self.catalog['patterns']
            catalog = parse_json(self.read(manifest['path']), manifest['path'])
            self.patterns = {row['id']: row for row in catalog['patterns']}

    def pattern_bundle(self, pattern_id):
        self.require_patterns()
        if pattern_id not in self.patterns:
            raise AtlasError(f'Unknown pattern ID: {pattern_id}')
        path = self.patterns[pattern_id]['paths']['bundle']
        bundle = parse_json(self.read(path), path)
        cases = [self.bundle(source['id']) for source in bundle['sourceCases']]
        return bundle, cases


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def merged_files(cases):
    records = {}
    for case in cases:
        for record in case['files']:
            key = record['path'].casefold()
            if key in records:
                records[key]['caseIds'].append(case['id'])
            else:
                records[key] = {**record, 'caseIds': [case['id']]}
    return list(records.values())


def read_source(atlas, records):
    sources = []
    for record in records:
        if record['role'] == 'source':
            data = atlas.read(record['path'])
            try:
                content = data.decode('utf-8')
            except UnicodeError as exc:
                raise AtlasError(f'Source is not UTF-8: {record["path"]}') from exc
            sources.append({**record, 'content': content})
    return sources


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
    offset = args.offset
    emit({"schemaVersion": 1, "provenance": atlas.provenance(), "query": args.query, "method": "keyword", "total": len(results), "offset": offset, "limit": args.limit, "hasMore": offset + args.limit < len(results), "results": results[offset:offset + args.limit]})


def show(atlas, args):
    bundle = atlas.bundle(args.case_id)
    result = {**bundle, "provenance": atlas.provenance()}
    if args.source:
        result["source"] = read_source(atlas, bundle['files'])
    emit(result)


def pattern_search(atlas, args):
    atlas.require_patterns()
    terms = list(dict.fromkeys(term.casefold() for term in re.split(r'[\s,，;；]+', args.query) if term))
    fields = ['id', 'title', 'category', 'experienceTypes', 'summary', 'mechanism', 'trigger', 'effect', 'useCases', 'avoid', 'constraints', 'composition', 'accessibility', 'parameters', 'sources', 'sourceCases']
    results = []
    for pattern in atlas.patterns.values():
        if args.category and pattern['category'].casefold() != args.category.casefold():
            continue
        if args.type and args.type not in pattern['experienceTypes']:
            continue
        case_ids = sorted({source['caseId'] for source in pattern['sources']})
        if args.case and args.case not in case_ids:
            continue
        source_cases = [{key: atlas.entries[case_id][key] for key in ('id', 'title', 'paths')} for case_id in case_ids]
        indexed = {**pattern, 'sourceCases': source_cases}
        haystacks = {field: json.dumps(indexed.get(field, ''), ensure_ascii=False).casefold() for field in fields}
        matches = [{'term': term, 'fields': [field for field in fields if term in haystacks[field]]} for term in terms]
        matches = [match for match in matches if match['fields']]
        if terms and not matches:
            continue
        score = sum(4 if field in {'id', 'title', 'useCases', 'mechanism'} else 1 if field in {'avoid', 'constraints'} else 2 for match in matches for field in match['fields'])
        result = {key: pattern[key] for key in ('id', 'title', 'category', 'summary', 'trigger', 'effect', 'useCases', 'avoid', 'constraints', 'composition', 'accessibility', 'sources', 'sourceFiles', 'paths')}
        result.update({'experienceTypes': pattern['experienceTypes'], 'sourceCases': source_cases, 'score': score, 'matches': matches})
        results.append(result)
    results.sort(key=lambda row: (-row['score'], row['id']))
    emit({'schemaVersion': 1, 'provenance': atlas.provenance(), 'query': args.query, 'filters': {'category': args.category, 'type': args.type, 'case': args.case}, 'method': 'keyword', 'total': len(results), 'offset': args.offset, 'limit': args.limit, 'hasMore': args.offset + args.limit < len(results), 'results': results[args.offset:args.offset + args.limit]})


def pattern_show(atlas, args):
    bundle, cases = atlas.pattern_bundle(args.pattern_id)
    result = {**bundle, 'sourceCaseBundles': cases, 'provenance': atlas.provenance()}
    if args.source:
        paths = set(bundle['pattern']['sourceFiles'])
        result['source'] = read_source(atlas, [record for record in merged_files(cases) if record['path'] in paths])
    emit(result)


def material_search(atlas, args):
    atlas.require_materials()
    terms = list(dict.fromkeys(term.casefold() for term in re.split(r'[\s,，;；]+', args.query) if term))
    fields = ['id', 'title', 'type', 'category', 'tags', 'summary', 'useCases', 'avoid', 'constraints']
    results = []
    for material in atlas.materials.values():
        if args.category and material['category'].casefold() != args.category.casefold():
            continue
        if args.type and material['type'].casefold() != args.type.casefold():
            continue
        haystacks = {field: json.dumps(material.get(field, ''), ensure_ascii=False).casefold() for field in fields}
        matches = [{'term': term, 'fields': [field for field in fields if term in haystacks[field]]} for term in terms]
        matches = [match for match in matches if match['fields']]
        if terms and not matches:
            continue
        score = sum(4 if field in {'id', 'title', 'tags', 'useCases'} else 1 if field in {'avoid', 'constraints'} else 2 for match in matches for field in match['fields'])
        results.append({**{key: material[key] for key in [*fields, 'paths']}, 'score': score, 'matches': matches})
    results.sort(key=lambda row: (-row['score'], row['id']))
    emit({'schemaVersion': 1, 'provenance': atlas.provenance(), 'query': args.query, 'filters': {'category': args.category, 'type': args.type}, 'method': 'keyword', 'total': len(results), 'offset': args.offset, 'limit': args.limit, 'hasMore': args.offset + args.limit < len(results), 'results': results[args.offset:args.offset + args.limit]})


def material_show(atlas, args):
    bundle = atlas.material_bundle(args.material_id)
    result = {**bundle, 'provenance': atlas.provenance()}
    if args.source:
        paths = set(bundle['sourceFiles'])
        result['source'] = read_source(atlas, [record for record in bundle['files'] if record['path'] in paths])
    emit(result)


def material_export(atlas, args):
    export(atlas, args, kind='material')


def pattern_export(atlas, args):
    bundle, cases = atlas.pattern_bundle(args.pattern_id)
    records = merged_files(cases)
    selected = [record for record in records if not args.code_only or record['role'] in {'source', 'context'}]
    out = Path(args.out).absolute()
    no_symlinks(out)
    out = out.resolve()
    if out.exists():
        raise AtlasError(f'Export requires a new directory; already exists: {out}')
    if any(record['path'].casefold() == 'atlas-export.json' for record in records):
        raise AtlasError('Source manifest conflicts with export metadata')
    metadata = {
        'schemaVersion': 1, 'kind': 'pattern', 'id': args.pattern_id,
        'provenance': atlas.provenance(),
        'paths': atlas.patterns[args.pattern_id]['paths'], 'codeOnly': args.code_only,
        'sourceFiles': bundle['pattern']['sourceFiles'], 'files': selected,
        'omitted': [record['path'] for record in records if record not in selected],
        'filesNotDownloaded': [{**record, 'url': atlas.url(record['path']) if not atlas.local else None} for record in records if record not in selected],
        'bundle': bundle, 'sourceCaseBundles': cases,
        'entrypoints': [{'caseId': source['id'], 'path': source['paths']['demo']} for source in bundle['sourceCases']],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir()
    try:
        for record in selected:
            data = atlas.read(record['path'])
            target = out.joinpath(*path_parts(record['path']))
            no_symlinks(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as handle:
                handle.write(data)
        with (out / 'atlas-export.json').open('x', encoding='utf-8', newline='\n') as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
    except Exception:
        no_symlinks(out)
        shutil.rmtree(out)
        raise
    emit({'kind': 'pattern', 'id': args.pattern_id, 'provenance': atlas.provenance(), 'directory': str(out), 'files': len(selected), 'sourceFiles': metadata['sourceFiles'], 'omitted': metadata['omitted'], 'entrypoints': metadata['entrypoints']})


def export(atlas, args, kind='case'):
    bundle_id = args.material_id if kind == 'material' else args.case_id
    bundle = atlas.material_bundle(bundle_id) if kind == 'material' else atlas.bundle(bundle_id)
    row = atlas.materials[bundle_id] if kind == 'material' else atlas.entries[bundle_id]
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
            target = out.joinpath(*path_parts(record["path"]))
            no_symlinks(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(data)
        metadata = {
            "schemaVersion": 1, "id": bundle_id, "provenance": atlas.provenance(),
            "paths": row["paths"],
            "codeOnly": args.code_only, "files": selected,
            "omitted": [r["path"] for r in bundle["files"] if r not in selected],
            "filesNotDownloaded": [{**r, "url": atlas.url(r["path"]) if not atlas.local else None} for r in bundle["files"] if r not in selected],
            "bundle": bundle,
        }
        if kind == 'material':
            metadata.update({'kind': kind, 'sourceFiles': bundle['sourceFiles']})
        with (out / "atlas-export.json").open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except Exception:
        shutil.rmtree(out)
        raise
    result = {"id": bundle_id, "provenance": atlas.provenance(), "directory": str(out), "files": len(selected), "omitted": metadata['omitted'], "entrypoint": metadata["paths"]["demo"]}
    if kind == 'material':
        result['kind'] = kind
    emit(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-root", help="Read a local Web Atlas checkout without network access")
    parser.add_argument("--ref", help="Retrieve an explicit full 40-character Git commit for reproduction")
    parser.add_argument("--session", help="Pin this workflow's resolved commit in a JSON file in the user's working directory")
    commands = parser.add_subparsers(dest="command", required=True)
    find = commands.add_parser("search", help="Search case metadata by keywords")
    find.add_argument("query", nargs="?", default="")
    find.add_argument("--category", help="Exact category filter")
    find.add_argument("--limit", type=int, default=5)
    find.add_argument("--offset", type=int, default=0, help="Skip this many ranked results when paging through the complete directory")
    detail = commands.add_parser("show", help="Read the full case bundle and optionally full source")
    detail.add_argument("case_id")
    detail.add_argument("--source", action="store_true")
    save = commands.add_parser("export", help="Download a case into a new directory")
    save.add_argument("case_id")
    save.add_argument("--out", required=True)
    save.add_argument("--code-only", action="store_true", help="Download source/context and explicitly list omitted media")
    pattern_find = commands.add_parser('pattern-search', help='Search reusable design patterns across source cases')
    pattern_find.add_argument('query', nargs='?', default='')
    pattern_find.add_argument('--category', help='Exact pattern category filter')
    pattern_find.add_argument('--type', choices=EXPERIENCE_TYPES, help='Experience type filter; matches patterns containing this type')
    pattern_find.add_argument('--case', help='Source case ID filter')
    pattern_find.add_argument('--limit', type=int, default=5)
    pattern_find.add_argument('--offset', type=int, default=0, help='Skip this many ranked patterns; continue until hasMore is false')
    pattern_detail = commands.add_parser('pattern-show', help='Read a complete pattern, its source case context and optionally relevant source')
    pattern_detail.add_argument('pattern_id')
    pattern_detail.add_argument('--source', action='store_true')
    pattern_save = commands.add_parser('pattern-export', help='Download a pattern and its related case demos/context')
    pattern_save.add_argument('pattern_id')
    pattern_save.add_argument('--out', required=True)
    pattern_save.add_argument('--code-only', action='store_true', help='Download source/context and explicitly list omitted media')
    material_find = commands.add_parser('material-search', help='Search content materials and their runnable examples')
    material_find.add_argument('query', nargs='?', default='')
    material_find.add_argument('--category', help='Exact material category filter')
    material_find.add_argument('--type', help='Exact resource type filter, such as component-library or font')
    material_find.add_argument('--limit', type=int, default=5)
    material_find.add_argument('--offset', type=int, default=0, help='Skip this many ranked materials; continue until hasMore is false')
    material_detail = commands.add_parser('material-show', help='Read a complete resource bundle and optionally full example source')
    material_detail.add_argument('material_id')
    material_detail.add_argument('--source', action='store_true')
    material_save = commands.add_parser('material-export', help='Download a resource and its runnable examples')
    material_save.add_argument('material_id')
    material_save.add_argument('--out', required=True)
    material_save.add_argument('--code-only', action='store_true', help='Download source/context and explicitly list omitted media')
    info = commands.add_parser("info", help="Report the active upstream version and directory counts")
    commands.add_parser("refresh", help="Resolve the latest default-branch commit and atomically refresh --session")
    args = parser.parse_args()
    if hasattr(args, "limit") and not 1 <= args.limit <= 100:
        parser.error("--limit must be from 1 to 100")
    if hasattr(args, 'offset') and args.offset < 0:
        parser.error('--offset must be a non-negative integer')
    if args.local_root and (args.ref or args.session):
        parser.error('--local-root is an independent offline mode; use it without --ref or --session')
    if args.command == 'refresh' and (not args.session or args.ref or args.local_root):
        parser.error('refresh requires --session and resolves the latest version; omit --ref and --local-root')
    try:
        atlas = Atlas(args)
        if args.command == "search":
            search(atlas, args)
        elif args.command == "show":
            show(atlas, args)
        elif args.command == "export":
            export(atlas, args)
        elif args.command == 'pattern-search':
            pattern_search(atlas, args)
        elif args.command == 'pattern-show':
            pattern_show(atlas, args)
        elif args.command == 'pattern-export':
            pattern_export(atlas, args)
        elif args.command == 'material-search':
            material_search(atlas, args)
        elif args.command == 'material-show':
            material_show(atlas, args)
        elif args.command == 'material-export':
            material_export(atlas, args)
        else:
            result = {"provenance": atlas.provenance(), "entryCount": len(atlas.entries), 'patternCount': atlas.catalog['patterns']['patternCount'], 'materialCount': atlas.catalog['materials']['materialCount']}
            if args.command == 'refresh':
                result.update({'previousRef': atlas.previous_ref, 'refChanged': atlas.previous_ref != atlas.ref})
            emit(result)
        return 0
    except (AtlasError, OSError, KeyError, TypeError) as exc:
        print(f"web-atlas: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
