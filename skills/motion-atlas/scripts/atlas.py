#!/usr/bin/env python3
"""Retrieve Motion Atlas references (cases, patterns, prompts, demos) without third-party packages."""

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
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SKILL_ROOT = Path(__file__).resolve().parent.parent
HASH = re.compile(r'^[0-9a-f]{64}$')
COMMIT = re.compile(r'^[0-9a-f]{40}$')
IDENTITY = re.compile(r'^[a-z0-9][a-z0-9-]*$')
TAXONOMY_GROUPS = ('carriers', 'sources', 'types', 'evidence', 'roles')
USER_AGENT = 'mibxr-motion-atlas-skill/1'
KINDS = {'case': 'cases', 'pattern': 'patterns'}


class AtlasError(Exception):
    pass


def path_parts(value):
    if not isinstance(value, str) or not value or re.search(r'[\\\x00<>:"|?*]', value):
        raise AtlasError(f'Invalid repository path: {value!r}')
    parts = value.split('/')
    if PurePosixPath(value).is_absolute() or any(p in ('', '.', '..') for p in parts):
        raise AtlasError(f'Unsafe repository path: {value!r}')
    if any(any(ord(c) < 32 for c in p) for p in parts):
        raise AtlasError(f'Invalid repository path: {value!r}')
    if any(re.search(r'[. ]$', p) or re.match(r'^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', p, re.I) for p in parts):
        raise AtlasError(f'Non-portable repository path: {value!r}')
    return parts


def no_symlinks(path):
    for component in [path, *path.parents]:
        if component.is_symlink() or (hasattr(component, 'is_junction') and component.is_junction()):
            raise AtlasError(f'Symbolic links and directory junctions are not supported: {component}')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_data(data, record):
    expected = record.get('sha256')
    count = record.get('bytes')
    if not isinstance(expected, str) or not HASH.fullmatch(expected):
        raise AtlasError(f"Missing SHA-256 for {record.get('path', 'resource')}")
    if not isinstance(count, int) or count < 0 or len(data) != count:
        raise AtlasError(f"Byte length mismatch: {record.get('path', 'resource')}")
    if digest(data) != expected:
        raise AtlasError(f"SHA-256 mismatch: {record.get('path', 'resource')}")


def parse_json(data, name):
    try:
        value = json.loads(data.decode('utf-8-sig'))
    except (ValueError, UnicodeError) as exc:
        raise AtlasError(f'Invalid UTF-8 JSON at {name}: {exc}') from exc
    if not isinstance(value, dict):
        raise AtlasError(f'Expected a JSON object at {name}')
    return value


def file_role(path):
    """Previews are screenshots for choosing; everything else in a demo directory is runnable source."""
    return 'preview' if path.startswith('previews/') else 'source'


def string_list(row, field, label):
    value = row.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise AtlasError(f'{label} has invalid {field}')
    return value


class Atlas:
    def __init__(self, args):
        lock = parse_json((SKILL_ROOT / 'upstream.lock.json').read_bytes(), 'upstream.lock.json')
        self.repository = lock['repository']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', self.repository):
            raise AtlasError('Invalid repository in upstream.lock.json')
        explicit_ref = args.ref
        if explicit_ref and not COMMIT.fullmatch(explicit_ref):
            raise AtlasError('--ref must use a full 40-character Git commit')
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
                raise AtlasError(f'Local checkout does not exist: {self.local}')
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
        self.base = f'https://raw.githubusercontent.com/{self.repository}/{self.ref}/'
        self.catalog = parse_json(self.read(lock['catalog']), lock['catalog'])
        if self.catalog.get('schemaVersion') != lock['schemaVersion']:
            raise AtlasError('Catalog schemaVersion is incompatible with this skill')
        if not HASH.fullmatch(str(self.catalog.get('contentVersion', ''))):
            raise AtlasError('Catalog contentVersion must be a SHA-256 digest')
        self.load_taxonomy()
        self.cases = self.load_rows('case')
        self.patterns = self.load_rows('pattern')
        counts = self.catalog.get('counts')
        if counts != {'cases': len(self.cases), 'patterns': len(self.patterns)}:
            raise AtlasError('Catalog counts differ from its case and pattern rows')
        self.check_links()
        # 与上游 scripts/lib/catalog.mjs 一致：按 "bundle:sha256" 排序后以换行连接再取摘要
        version = '\n'.join(sorted(f"{row['bundle']}:{row['bundleSha256']}" for row in [*self.cases.values(), *self.patterns.values()]))
        if digest(version.encode('utf-8')) != self.catalog['contentVersion']:
            raise AtlasError('Catalog contentVersion differs from its case and pattern bundle hashes')
        if saved_session and args.command != 'refresh' and saved_session['contentVersion'] != self.catalog['contentVersion']:
            raise AtlasError('Session catalog contentVersion differs from the pinned catalog')
        if self.session and (saved_session is None or args.command == 'refresh'):
            self.write_session(replace=saved_session is not None)

    def resolve_latest(self):
        api = f'https://api.github.com/repos/{self.repository}'

        def request_json(url):
            request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/vnd.github+json'})
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
        return self.base + urllib.parse.quote(path, safe='/')

    def read(self, path):
        parts = path_parts(path)
        if self.local:
            target = self.local.joinpath(*parts)
            no_symlinks(target)
            try:
                return target.read_bytes()
            except OSError as exc:
                raise AtlasError(f'Cannot read local file {path}: {exc}') from exc
        request = urllib.request.Request(self.url(path), headers={'User-Agent': USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (OSError, urllib.error.URLError) as exc:
            raise AtlasError(f'Cannot retrieve {path} at {self.ref}: {exc}') from exc

    def provenance(self):
        return {
            'repository': self.repository,
            'ref': self.ref if self.local is None else None,
            'localRoot': str(self.local) if self.local else None,
            'contentVersion': self.catalog['contentVersion'],
            'schemaVersion': self.catalog['schemaVersion'],
            'resolution': self.resolution,
            'defaultBranch': self.default_branch,
            'session': str(self.session) if self.session else None,
        }

    # ---------- 目录校验 ----------
    def load_taxonomy(self):
        taxonomy = self.catalog.get('taxonomy')
        if not isinstance(taxonomy, dict):
            raise AtlasError('Catalog has no taxonomy')
        for group in TAXONOMY_GROUPS:
            labels = taxonomy.get(group)
            if not isinstance(labels, dict) or not labels or any(not isinstance(k, str) or not isinstance(v, str) for k, v in labels.items()):
                raise AtlasError(f'Catalog taxonomy {group} is invalid')
        self.taxonomy = taxonomy

    def load_rows(self, kind):
        plural = KINDS[kind]
        rows = self.catalog.get(plural)
        if not isinstance(rows, list):
            raise AtlasError(f'Catalog {plural} must be a list')
        table = {}
        others = self.cases if kind == 'pattern' else {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not IDENTITY.fullmatch(row['id']):
                raise AtlasError(f'Catalog contains an invalid {kind} ID')
            row_id = row['id']
            label = f'{kind.capitalize()} {row_id}'
            if row_id in others:
                raise AtlasError(f'Duplicate ID across cases and patterns: {row_id}')
            if row_id in table:
                raise AtlasError(f'Duplicate {kind} ID: {row_id}')
            if row.get('bundle') != f'agent/{plural}/{row_id}.json':
                raise AtlasError(f'{label} bundle path differs from its identity')
            if not HASH.fullmatch(str(row.get('bundleSha256', ''))):
                raise AtlasError(f'{label} has an invalid bundleSha256')
            for field in ('title', 'summary'):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise AtlasError(f'{label} has no {field}')
            self.check_terms(row, 'carriers', 'carriers', label)
            if kind == 'case':
                for field in ('tags', 'useCases', 'avoid', 'patternIds'):
                    string_list(row, field, label)
                if row.get('source') not in self.taxonomy['sources'] or row.get('evidence') not in self.taxonomy['evidence']:
                    raise AtlasError(f'{label} has an unknown source or evidence level')
                if not isinstance(row.get('seekable'), bool):
                    raise AtlasError(f'{label} has invalid seekable')
            else:
                self.check_terms(row, 'types', 'types', label)
                for field in ('sourceCases', 'pairsWellWith'):
                    string_list(row, field, label)
                if row.get('role') not in self.taxonomy['roles']:
                    raise AtlasError(f'{label} has an unknown composition role')
                if not row['sourceCases']:
                    raise AtlasError(f'{label} has no source case')
            table[row_id] = row
        return table

    def check_terms(self, row, field, group, label):
        values = string_list(row, field, label)
        if not values or any(value not in self.taxonomy[group] for value in values) or len(set(values)) != len(values):
            raise AtlasError(f'{label} has invalid {field}')

    def check_links(self):
        for case_id, row in self.cases.items():
            if any(pattern_id not in self.patterns for pattern_id in row['patternIds']):
                raise AtlasError(f'Case {case_id} refers to an unknown pattern')
        for pattern_id, row in self.patterns.items():
            if any(case_id not in self.cases for case_id in row['sourceCases']):
                raise AtlasError(f'Pattern {pattern_id} refers to an unknown source case')
            if any(other not in self.patterns or other == pattern_id for other in row['pairsWellWith']):
                raise AtlasError(f'Pattern {pattern_id} has an unknown or self-referential pairsWellWith pattern')

    def check_filter(self, group, value, option):
        if value is not None and value not in self.taxonomy[group]:
            choices = ', '.join(self.taxonomy[group])
            raise AtlasError(f'Unknown {option} {value!r}; this version supports: {choices}')

    def labels(self, group, values):
        return [self.taxonomy[group].get(value, value) for value in values]

    # ---------- 资料包 ----------
    def bundle(self, kind, bundle_id):
        table = self.cases if kind == 'case' else self.patterns
        if bundle_id not in table:
            raise AtlasError(f'Unknown {kind} ID: {bundle_id}')
        row = table[bundle_id]
        data = self.read(row['bundle'])
        if digest(data) != row['bundleSha256']:
            raise AtlasError(f'{kind.capitalize()} bundle SHA-256 mismatch: {bundle_id}')
        bundle = parse_json(data, row['bundle'])
        body = bundle.get('entry' if kind == 'case' else 'pattern')
        if bundle.get('schemaVersion') != self.catalog['schemaVersion'] or bundle.get('kind') != kind or bundle.get('id') != bundle_id:
            raise AtlasError(f'{kind.capitalize()} bundle identity or schemaVersion mismatch: {bundle_id}')
        if not isinstance(body, dict) or body.get('id') != bundle_id or body.get('title') != row['title']:
            raise AtlasError(f'{kind.capitalize()} bundle metadata differs from its pinned catalog: {bundle_id}')
        documents = bundle.get('documents')
        if not isinstance(documents, dict) or not isinstance(documents.get('prompt'), str) or any(value is not None and not isinstance(value, str) for value in documents.values()):
            raise AtlasError(f'{kind.capitalize()} bundle documents are invalid: {bundle_id}')
        files = bundle.get('files')
        if not isinstance(files, list) or not files:
            raise AtlasError(f'{kind.capitalize()} bundle has no files: {bundle_id}')
        seen = set()
        for record in files:
            if not isinstance(record, dict):
                raise AtlasError(f'Invalid file record in {bundle_id}')
            path_parts(record.get('path'))
            key = record['path'].casefold()
            if key in seen:
                raise AtlasError(f"Duplicate file path: {record['path']}")
            seen.add(key)
            if not HASH.fullmatch(str(record.get('sha256', ''))) or not isinstance(record.get('bytes'), int) or record['bytes'] < 0:
                raise AtlasError(f"Invalid file integrity metadata: {record['path']}")
        entrypoint = bundle.get('entrypoint')
        path_parts(entrypoint)
        if entrypoint != body.get('demo') or entrypoint.casefold() not in seen:
            raise AtlasError(f'{kind.capitalize()} entrypoint is absent from its file manifest: {bundle_id}')
        if kind == 'pattern':
            sources = bundle.get('sourceCases')
            expected = self.patterns[bundle_id]['sourceCases']
            if not isinstance(sources, list) or [source.get('caseId') for source in sources if isinstance(source, dict)] != expected:
                raise AtlasError(f'Pattern source cases differ from its pinned catalog: {bundle_id}')
            if any(source.get('bundle') != f"agent/cases/{source['caseId']}.json" for source in sources):
                raise AtlasError(f'Pattern source case bundle path is invalid: {bundle_id}')
        return bundle

    def files(self, bundle):
        return [{**record, 'role': file_role(record['path'])} for record in bundle['files']]


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def terms_of(query):
    return list(dict.fromkeys(term.casefold() for term in re.split(r'[\s,，;；、]+', query) if term))


def rank(rows, terms, fields, strong, weak):
    results = []
    for row, indexed in rows:
        haystacks = {field: json.dumps(indexed.get(field, ''), ensure_ascii=False).casefold() for field in fields}
        matches = [{'term': term, 'fields': [field for field in fields if term in haystacks[field]]} for term in terms]
        matches = [match for match in matches if match['fields']]
        if terms and not matches:
            continue
        score = sum(4 if field in strong else 1 if field in weak else 2 for match in matches for field in match['fields'])
        results.append({**row, 'score': score, 'matches': matches})
    results.sort(key=lambda row: (-row['score'], row['id']))
    return results


def page(atlas, args, results, filters):
    return {
        'schemaVersion': 1, 'contentVersion': atlas.catalog['contentVersion'], 'provenance': atlas.provenance(),
        'query': args.query, 'filters': filters, 'method': 'keyword', 'total': len(results),
        'offset': args.offset, 'limit': args.limit, 'hasMore': args.offset + args.limit < len(results),
        'results': results[args.offset:args.offset + args.limit],
    }


def search(atlas, args):
    atlas.check_filter('carriers', args.carrier, '--carrier')
    atlas.check_filter('evidence', args.evidence, '--evidence')
    atlas.check_filter('sources', args.origin, '--origin')
    rows = []
    for row in atlas.cases.values():
        if args.carrier and args.carrier not in row['carriers']:
            continue
        if args.evidence and row['evidence'] != args.evidence:
            continue
        if args.origin and row['source'] != args.origin:
            continue
        if args.seekable and not row['seekable']:
            continue
        labels = {'carrierLabels': atlas.labels('carriers', row['carriers']), 'sourceLabel': atlas.taxonomy['sources'][row['source']], 'evidenceLabel': atlas.taxonomy['evidence'][row['evidence']]}
        rows.append(({**row, **labels}, {**row, **labels}))
    fields = ['id', 'title', 'tags', 'useCases', 'summary', 'carriers', 'carrierLabels', 'sourceLabel', 'evidenceLabel', 'patternIds', 'avoid']
    results = rank(rows, terms_of(args.query), fields, {'id', 'title', 'tags', 'useCases'}, {'avoid'})
    emit(page(atlas, args, results, {'carrier': args.carrier, 'evidence': args.evidence, 'origin': args.origin, 'seekable': args.seekable}))


def pattern_search(atlas, args):
    atlas.check_filter('types', args.type, '--type')
    atlas.check_filter('carriers', args.carrier, '--carrier')
    atlas.check_filter('roles', args.role, '--role')
    if args.case and args.case not in atlas.cases:
        raise AtlasError(f'Unknown case ID for --case: {args.case}')
    rows = []
    for row in atlas.patterns.values():
        if args.type and args.type not in row['types']:
            continue
        if args.carrier and args.carrier not in row['carriers']:
            continue
        if args.role and row['role'] != args.role:
            continue
        if args.case and args.case not in row['sourceCases']:
            continue
        labels = {'typeLabels': atlas.labels('types', row['types']), 'carrierLabels': atlas.labels('carriers', row['carriers']), 'roleLabel': atlas.taxonomy['roles'][row['role']],
                  'sourceCaseTitles': [atlas.cases[case_id]['title'] for case_id in row['sourceCases']]}
        rows.append(({**row, **labels}, {**row, **labels}))
    fields = ['id', 'title', 'summary', 'types', 'typeLabels', 'carriers', 'carrierLabels', 'role', 'roleLabel', 'sourceCases', 'sourceCaseTitles', 'pairsWellWith']
    results = rank(rows, terms_of(args.query), fields, {'id', 'title', 'typeLabels'}, {'pairsWellWith'})
    emit(page(atlas, args, results, {'type': args.type, 'carrier': args.carrier, 'role': args.role, 'case': args.case}))


def read_sources(atlas, records):
    sources = []
    for record in records:
        if record['role'] != 'source':
            continue
        data = atlas.read(record['path'])
        verify_data(data, record)
        try:
            content = data.decode('utf-8')
        except UnicodeError as exc:
            raise AtlasError(f"Source is not UTF-8: {record['path']}") from exc
        sources.append({**record, 'content': content})
    return sources


def show(atlas, args, kind='case'):
    bundle_id = args.case_id if kind == 'case' else args.pattern_id
    bundle = atlas.bundle(kind, bundle_id)
    result = {**bundle, 'files': atlas.files(bundle), 'catalogRow': (atlas.cases if kind == 'case' else atlas.patterns)[bundle_id], 'provenance': atlas.provenance()}
    if kind == 'pattern':
        # 来源案例只给目录摘要；需要完整上下文时再对该案例执行 show
        result['sourceCaseSummaries'] = [atlas.cases[case_id] for case_id in atlas.patterns[bundle_id]['sourceCases']]
    if args.source:
        result['source'] = read_sources(atlas, result['files'])
    emit(result)


def pattern_show(atlas, args):
    show(atlas, args, kind='pattern')


def export(atlas, args, kind='case'):
    bundle_id = args.case_id if kind == 'case' else args.pattern_id
    bundle = atlas.bundle(kind, bundle_id)
    records = atlas.files(bundle)
    selected = [record for record in records if not args.code_only or record['role'] == 'source']
    body = bundle['entry' if kind == 'case' else 'pattern']
    documents = [{'path': f"prompts/{KINDS[kind]}/{bundle_id}.md", 'role': 'prompt', 'content': bundle['documents']['prompt']}]
    if bundle['documents'].get('research') and isinstance(body.get('research'), str):
        documents.append({'path': body['research'], 'role': 'research', 'content': bundle['documents']['research']})
    reserved = {record['path'].casefold() for record in records}
    for document in documents:
        path_parts(document['path'])
        if document['path'].casefold() in reserved or document['path'].casefold() == 'atlas-export.json':
            raise AtlasError(f"Document path conflicts with the file manifest: {document['path']}")
    if any(record['path'].casefold() == 'atlas-export.json' for record in records):
        raise AtlasError('Source manifest conflicts with export metadata')
    out = Path(args.out).absolute()
    no_symlinks(out)
    if out.exists():
        raise AtlasError(f'Export requires a new directory; already exists: {out}')
    omitted = [record for record in records if record not in selected]
    metadata = {
        'schemaVersion': 1, 'kind': kind, 'id': bundle_id, 'provenance': atlas.provenance(),
        'entrypoint': bundle['entrypoint'], 'codeOnly': args.code_only, 'files': selected,
        'documents': [{key: document[key] for key in ('path', 'role')} for document in documents],
        'omitted': [record['path'] for record in omitted],
        'filesNotDownloaded': [{**record, 'url': atlas.url(record['path']) if not atlas.local else None} for record in omitted],
        'bundle': bundle,
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
        for document in documents:
            target = out.joinpath(*path_parts(document['path']))
            no_symlinks(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('x', encoding='utf-8', newline='\n') as handle:
                handle.write(document['content'])
        with (out / 'atlas-export.json').open('x', encoding='utf-8', newline='\n') as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
    except Exception:
        no_symlinks(out)
        shutil.rmtree(out)
        raise
    emit({'kind': kind, 'id': bundle_id, 'provenance': atlas.provenance(), 'directory': str(out), 'entrypoint': bundle['entrypoint'],
          'files': len(selected), 'bytes': sum(record['bytes'] for record in selected), 'documents': metadata['documents'], 'omitted': metadata['omitted']})


def pattern_export(atlas, args):
    export(atlas, args, kind='pattern')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-root', help='Read a local Motion Atlas checkout without network access')
    parser.add_argument('--ref', help='Retrieve an explicit full 40-character Git commit for reproduction')
    parser.add_argument('--session', help="Pin this workflow's resolved commit in a JSON file in the user's working directory")
    commands = parser.add_subparsers(dest='command', required=True)
    find = commands.add_parser('search', help='Search complete cases (video / console / showcase works)')
    find.add_argument('query', nargs='?', default='')
    find.add_argument('--carrier', help='Carrier filter, such as video, console or showcase')
    find.add_argument('--evidence', help='Evidence filter, such as observed, adapted, inferred or original')
    find.add_argument('--origin', help='Source filter, such as reference, game or original')
    find.add_argument('--seekable', action='store_true', help='Only cases whose demo exposes the render(t) protocol')
    find.add_argument('--limit', type=int, default=5)
    find.add_argument('--offset', type=int, default=0, help='Skip this many ranked results; continue until hasMore is false')
    detail = commands.add_parser('show', help='Read a complete case bundle and optionally its full demo source')
    detail.add_argument('case_id')
    detail.add_argument('--source', action='store_true')
    save = commands.add_parser('export', help='Download and hash-verify a case demo, prompt and research into a new directory')
    save.add_argument('case_id')
    save.add_argument('--out', required=True)
    save.add_argument('--code-only', action='store_true', help='Skip preview screenshots and list them as omitted')
    pattern_find = commands.add_parser('pattern-search', help='Search reusable motion patterns')
    pattern_find.add_argument('query', nargs='?', default='')
    pattern_find.add_argument('--type', help='Pattern type, such as transition, rhythm, feedback or hud')
    pattern_find.add_argument('--carrier', help='Carrier filter, such as video, console or showcase')
    pattern_find.add_argument('--role', help='Composition role: foundation, support or accent')
    pattern_find.add_argument('--case', help='Source case ID filter')
    pattern_find.add_argument('--limit', type=int, default=5)
    pattern_find.add_argument('--offset', type=int, default=0, help='Skip this many ranked patterns; continue until hasMore is false')
    pattern_detail = commands.add_parser('pattern-show', help='Read a complete pattern bundle and optionally its demo source')
    pattern_detail.add_argument('pattern_id')
    pattern_detail.add_argument('--source', action='store_true')
    pattern_save = commands.add_parser('pattern-export', help='Download and hash-verify a pattern demo and prompt into a new directory')
    pattern_save.add_argument('pattern_id')
    pattern_save.add_argument('--out', required=True)
    pattern_save.add_argument('--code-only', action='store_true', help='Skip preview screenshots and list them as omitted')
    commands.add_parser('info', help='Verify the catalog and report the active upstream version and taxonomy')
    commands.add_parser('refresh', help='Resolve the latest default-branch commit and atomically refresh --session')
    args = parser.parse_args()
    if hasattr(args, 'limit') and not 1 <= args.limit <= 100:
        parser.error('--limit must be from 1 to 100')
    if hasattr(args, 'offset') and args.offset < 0:
        parser.error('--offset must be a non-negative integer')
    if args.local_root and (args.ref or args.session):
        parser.error('--local-root is an independent offline mode; use it without --ref or --session')
    if args.command == 'refresh' and (not args.session or args.ref or args.local_root):
        parser.error('refresh requires --session and resolves the latest version; omit --ref and --local-root')
    try:
        atlas = Atlas(args)
        handlers = {'search': search, 'show': show, 'export': export, 'pattern-search': pattern_search, 'pattern-show': pattern_show, 'pattern-export': pattern_export}
        if args.command in handlers:
            handlers[args.command](atlas, args)
        else:
            result = {'provenance': atlas.provenance(), 'caseCount': len(atlas.cases), 'patternCount': len(atlas.patterns),
                      'taxonomy': atlas.taxonomy, 'protocol': atlas.catalog.get('protocol')}
            if args.command == 'refresh':
                result.update({'previousRef': atlas.previous_ref, 'refChanged': atlas.previous_ref != atlas.ref})
            emit(result)
        return 0
    except (AtlasError, OSError, KeyError, TypeError) as exc:
        print(f'motion-atlas: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
