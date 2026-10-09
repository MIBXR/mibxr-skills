#!/usr/bin/env python3
"""Retrieve Design Atlas references without a website UI or third-party packages."""

import argparse
import hashlib
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
HASH = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
ROLES = {"source", "asset", "context", "preview"}
PATTERN_ROLES = {"foundation", "support", "accent"}
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
                if not COMMIT.fullmatch(str(saved_session.get('ref', ''))) or not HASH.fullmatch(str(saved_session.get('contentVersion', ''))):
                    raise AtlasError('Session ref or contentVersion is invalid')
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
        self.patterns = None
        self.pattern_catalog = None
        version = ''.join(f"{case_id}:{self.entries[case_id]['bundleSha256']}\n" for case_id in sorted(self.entries))
        if 'patterns' in self.catalog:
            self.load_patterns(self.catalog['patterns'])
            version += f"patterns:{self.pattern_catalog['contentVersion']}\n"
        if digest(version.encode('utf-8')) != self.catalog['contentVersion']:
            raise AtlasError('Catalog contentVersion differs from its case and pattern hashes')
        if args.command.startswith('pattern-'):
            self.require_patterns()
        if saved_session and args.command != 'refresh' and saved_session['contentVersion'] != self.catalog['contentVersion']:
            raise AtlasError('Session catalog contentVersion differs from the pinned catalog')
        if self.session and (saved_session is None or args.command == 'refresh'):
            self.write_session(replace=saved_session is not None)

    def resolve_latest(self):
        api = f'https://api.github.com/repos/{self.repository}'
        def request_json(url):
            request = urllib.request.Request(url, headers={'User-Agent': 'mibxr-design-atlas-skill/1', 'Accept': 'application/vnd.github+json'})
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
            'contentVersion': self.catalog['contentVersion'],
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
            "resolution": self.resolution,
            "defaultBranch": self.default_branch,
            "session": str(self.session) if self.session else None,
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

    def load_patterns(self, manifest):
        if not isinstance(manifest, dict) or manifest.get('path') != 'agent/patterns.json':
            raise AtlasError('Invalid patterns manifest path')
        data = self.read(manifest['path'])
        verify_data(data, manifest)
        catalog = parse_json(data, manifest['path'])
        if catalog.get('schemaVersion') != 1:
            raise AtlasError('Pattern catalog schemaVersion is incompatible with this skill')
        if catalog.get('repository') not in {self.repository, f'https://github.com/{self.repository}'}:
            raise AtlasError('Pattern catalog repository differs from the case catalog')
        rows = catalog.get('patterns')
        if not isinstance(rows, list) or catalog.get('patternCount') != len(rows) or manifest.get('patternCount') != len(rows):
            raise AtlasError('Pattern catalog patterns or patternCount are invalid')
        self.patterns = {}
        for row in rows:
            if not isinstance(row, dict):
                raise AtlasError('Pattern catalog contains an invalid pattern')
            pattern_id = row.get('id')
            if not isinstance(pattern_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', pattern_id):
                raise AtlasError('Pattern catalog contains an invalid pattern ID')
            if pattern_id in self.patterns:
                raise AtlasError(f'Duplicate pattern ID: {pattern_id}')
            if row.get('paths', {}).get('bundle') != f'agent/patterns/{pattern_id}.json':
                raise AtlasError(f'Pattern bundle path differs from its identity: {pattern_id}')
            if not HASH.fullmatch(str(row.get('bundleSha256', ''))):
                raise AtlasError(f'Invalid pattern bundleSha256: {pattern_id}')
            for field in ('title', 'category', 'summary', 'mechanism', 'trigger', 'effect', 'prompt'):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise AtlasError(f'Pattern {pattern_id} has no {field}')
            for field in ('useCases', 'avoid', 'constraints', 'sourceFiles'):
                if not isinstance(row.get(field), list) or any(not isinstance(value, str) for value in row[field]):
                    raise AtlasError(f'Pattern {pattern_id} has invalid {field}')
            if 'experienceTypes' in row:
                types = row['experienceTypes']
                if not isinstance(types, list) or not types or any(value not in EXPERIENCE_TYPES for value in types) or len(set(types)) != len(types):
                    raise AtlasError(f'Pattern {pattern_id} has invalid experienceTypes')
            for path in row['sourceFiles']:
                path_parts(path)
            if not row['sourceFiles'] or len({p.casefold() for p in row['sourceFiles']}) != len(row['sourceFiles']):
                raise AtlasError(f'Pattern {pattern_id} has missing or duplicate sourceFiles')
            sources = row.get('sources')
            if not isinstance(sources, list) or not sources:
                raise AtlasError(f'Pattern {pattern_id} has no source case')
            for source in sources:
                if not isinstance(source, dict) or source.get('caseId') not in self.entries:
                    raise AtlasError(f'Pattern {pattern_id} refers to an unknown source case')
                if source.get('evidence') not in {'observed', 'adapted', 'inferred'}:
                    raise AtlasError(f'Pattern {pattern_id} has invalid source evidence')
                if any(not isinstance(source.get(field), str) or not source[field].strip() for field in ('locator', 'observation')):
                    raise AtlasError(f'Pattern {pattern_id} has incomplete source evidence')
            composition = row.get('composition')
            if not isinstance(composition, dict) or composition.get('role') not in PATTERN_ROLES or not isinstance(composition.get('notes'), str):
                raise AtlasError(f'Pattern {pattern_id} has invalid composition')
            for field in ('pairsWellWith', 'conflicts'):
                if not isinstance(composition.get(field), list) or any(not isinstance(value, str) for value in composition[field]):
                    raise AtlasError(f'Pattern {pattern_id} has invalid composition {field}')
            accessibility = row.get('accessibility')
            if not isinstance(accessibility, dict) or any(not isinstance(accessibility.get(field), str) for field in ('keyboard', 'reducedMotion')):
                raise AtlasError(f'Pattern {pattern_id} has invalid accessibility constraints')
            parameters = row.get('parameters')
            if not isinstance(parameters, list) or any(not isinstance(parameter, dict) or any(not isinstance(parameter.get(field), str) for field in ('name', 'value', 'note')) for parameter in parameters):
                raise AtlasError(f'Pattern {pattern_id} has invalid parameters')
            self.patterns[pattern_id] = row
        for pattern_id, row in self.patterns.items():
            for field in ('pairsWellWith', 'conflicts'):
                if any(other not in self.patterns or other == pattern_id for other in row['composition'][field]):
                    raise AtlasError(f'Pattern {pattern_id} has an unknown or self-referential {field} pattern')
        version = ''.join(f"{pattern_id}:{self.patterns[pattern_id]['bundleSha256']}\n" for pattern_id in sorted(self.patterns))
        if digest(version.encode('utf-8')) != catalog.get('contentVersion') or manifest.get('contentVersion') != catalog.get('contentVersion'):
            raise AtlasError('Pattern catalog contentVersion differs from its manifest or bundle hashes')
        self.pattern_catalog = catalog

    def require_patterns(self):
        if self.patterns is None:
            raise AtlasError('This pinned Atlas version has no design patterns library. Keep it for case commands; use --session SESSION_FILE refresh, a newer --ref, or an updated --local-root to access pattern commands.')

    def pattern_bundle(self, pattern_id):
        self.require_patterns()
        if pattern_id not in self.patterns:
            raise AtlasError(f'Unknown pattern ID: {pattern_id}')
        row = self.patterns[pattern_id]
        data = self.read(row['paths']['bundle'])
        if digest(data) != row['bundleSha256']:
            raise AtlasError(f'Pattern bundle SHA-256 mismatch: {pattern_id}')
        bundle = parse_json(data, row['paths']['bundle'])
        pattern = {key: value for key, value in row.items() if key not in {'paths', 'bundleSha256'}}
        if bundle.get('schemaVersion') != 1 or bundle.get('id') != pattern_id or bundle.get('pattern') != pattern:
            raise AtlasError(f'Pattern bundle identity, schemaVersion or metadata mismatch: {pattern_id}')
        sources = bundle.get('sourceCases')
        expected = {source['caseId'] for source in row['sources']}
        if not isinstance(sources, list) or len(sources) != len(expected):
            raise AtlasError(f'Pattern source case identities are invalid: {pattern_id}')
        seen = set()
        cases = []
        for source in sources:
            if not isinstance(source, dict) or source.get('id') not in expected or source['id'] in seen:
                raise AtlasError(f'Pattern source case identity mismatch: {pattern_id}')
            case_id = source['id']
            seen.add(case_id)
            entry = self.entries[case_id]
            if source.get('title') != entry['title'] or source.get('bundleSha256') != entry['bundleSha256'] or source.get('paths') != {key: entry['paths'][key] for key in ('bundle', 'demo')}:
                raise AtlasError(f'Pattern source case metadata or SHA-256 differs from the pinned case catalog: {case_id}')
            case = self.bundle(case_id)
            if case['entry'].get('title') != source['title'] or case['entry'].get('demo') != source['paths']['demo']:
                raise AtlasError(f'Pattern source case title or demo differs from its verified case bundle: {case_id}')
            if not any(record['path'] == source['paths']['demo'] and record['role'] == 'source' for record in case['files']):
                raise AtlasError(f'Pattern source case demo is absent from its source manifest: {case_id}')
            cases.append(case)
        records = merged_files(cases)
        files = {record['path'] for record in records}
        if any(path not in files for path in row['sourceFiles']):
            raise AtlasError(f'Pattern sourceFiles are absent from verified source case manifests: {pattern_id}')
        return bundle, cases


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def merged_files(cases):
    records = {}
    for case in cases:
        for record in case['files']:
            key = record['path'].casefold()
            if key in records:
                previous = records[key]
                if any(previous[field] != record[field] for field in ('path', 'sha256', 'bytes', 'role')):
                    raise AtlasError(f'Source case manifests disagree on shared file: {record["path"]}')
                previous['caseIds'].append(case['id'])
            else:
                records[key] = {**record, 'caseIds': [case['id']]}
    return list(records.values())


def read_source(atlas, records):
    sources = []
    for record in records:
        if record['role'] == 'source':
            data = atlas.read(record['path'])
            verify_data(data, record)
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
    emit({"schemaVersion": 1, "contentVersion": atlas.catalog['contentVersion'], "provenance": atlas.provenance(), "query": args.query, "method": "keyword", "total": len(results), "offset": offset, "limit": args.limit, "hasMore": offset + args.limit < len(results), "results": results[offset:offset + args.limit]})


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


def pattern_search(atlas, args):
    atlas.require_patterns()
    if args.type and not any('experienceTypes' in pattern for pattern in atlas.patterns.values()):
        raise AtlasError('This pinned Atlas version has no experience type classifications. Use --session SESSION_FILE refresh, a newer --ref, or an updated --local-root to filter by --type.')
    terms = list(dict.fromkeys(term.casefold() for term in re.split(r'[\s,，;；]+', args.query) if term))
    fields = ['id', 'title', 'category', 'experienceTypes', 'summary', 'mechanism', 'trigger', 'effect', 'useCases', 'avoid', 'constraints', 'composition', 'accessibility', 'parameters', 'sources', 'sourceCases']
    results = []
    for pattern in atlas.patterns.values():
        if args.category and pattern['category'].casefold() != args.category.casefold():
            continue
        if args.type and args.type not in pattern.get('experienceTypes', []):
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
        result.update({'experienceTypes': pattern.get('experienceTypes', []), 'sourceCases': source_cases, 'score': score, 'matches': matches})
        results.append(result)
    results.sort(key=lambda row: (-row['score'], row['id']))
    emit({'schemaVersion': 1, 'contentVersion': atlas.catalog['contentVersion'], 'patternContentVersion': atlas.pattern_catalog['contentVersion'], 'provenance': atlas.provenance(), 'query': args.query, 'filters': {'category': args.category, 'type': args.type, 'case': args.case}, 'method': 'keyword', 'total': len(results), 'offset': args.offset, 'limit': args.limit, 'hasMore': args.offset + args.limit < len(results), 'results': results[args.offset:args.offset + args.limit]})


def pattern_show(atlas, args):
    bundle, cases = atlas.pattern_bundle(args.pattern_id)
    result = {**bundle, 'sourceCaseBundles': cases, 'provenance': atlas.provenance()}
    if args.source:
        paths = set(bundle['pattern']['sourceFiles'])
        result['source'] = read_source(atlas, [record for record in merged_files(cases) if record['path'] in paths])
    emit(result)


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
        'provenance': atlas.provenance(), 'patternContentVersion': atlas.pattern_catalog['contentVersion'],
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
            verify_data(data, record)
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
    emit({'kind': 'pattern', 'id': args.pattern_id, 'provenance': atlas.provenance(), 'directory': str(out), 'files': len(selected), 'bytes': sum(record['bytes'] for record in selected), 'sourceFiles': metadata['sourceFiles'], 'omitted': metadata['omitted'], 'entrypoints': metadata['entrypoints']})


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
    save = commands.add_parser("export", help="Download and hash-verify a case into a new directory")
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
    pattern_save = commands.add_parser('pattern-export', help='Download and verify a pattern and its related case demos/context')
    pattern_save.add_argument('pattern_id')
    pattern_save.add_argument('--out', required=True)
    pattern_save.add_argument('--code-only', action='store_true', help='Download source/context and explicitly list omitted media')
    info = commands.add_parser("info", help="Verify the catalog and report the active upstream version")
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
        else:
            result = {"provenance": atlas.provenance(), "entryCount": len(atlas.entries), 'patternCount': len(atlas.patterns) if atlas.patterns is not None else None}
            if args.command == 'refresh':
                result.update({'previousRef': atlas.previous_ref, 'refChanged': atlas.previous_ref != atlas.ref})
            emit(result)
        return 0
    except (AtlasError, OSError, KeyError, TypeError) as exc:
        print(f"design-atlas: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
