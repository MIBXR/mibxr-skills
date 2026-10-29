#!/usr/bin/env python3
"""Retrieve Motion Atlas references without a website UI or third-party packages."""

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
CODE_EXTENSIONS = {
    '.html', '.htm', '.js', '.mjs', '.cjs', '.css', '.json', '.md', '.txt', '.svg',
    '.glsl', '.frag', '.vert', '.wgsl', '.xml', '.csv',
}


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
        self.entries = {
            entry['id']: {**entry, 'kind': kind}
            for kind in ('cases', 'patterns', 'materials') for entry in self.catalog[kind]
        }
        if self.session and (saved_session is None or args.command == 'refresh'):
            self.write_session(replace=saved_session is not None)

    def resolve_latest(self):
        api = f'https://api.github.com/repos/{self.repository}'
        def request_json(url):
            request = urllib.request.Request(url, headers={'User-Agent': 'mibxr-motion-atlas-skill/1', 'Accept': 'application/vnd.github+json'})
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
        request = urllib.request.Request(self.url(path), headers={"User-Agent": "mibxr-motion-atlas-skill/1"})
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

    def bundle(self, entry_id):
        if entry_id not in self.entries:
            raise AtlasError(f"Unknown case, pattern or material ID: {entry_id}")
        path = self.entries[entry_id]['bundle']
        return parse_json(self.read(path), path)


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def query_terms(query):
    terms = []
    for token in re.split(r'[\s,\uff0c\u3001]+', query.casefold()):
        if not token:
            continue
        terms.append(token)
        for text in re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]+', token):
            if len(text) > 2:
                terms.extend(text[i:i + 2] for i in range(len(text) - 1))
    return list(dict.fromkeys(terms))


def search(atlas, args):
    terms = query_terms(args.query)
    taxonomy = atlas.catalog['taxonomy']
    results = []
    for entry in atlas.entries.values():
        if args.kind and entry['kind'] != args.kind:
            continue
        if args.carrier and args.carrier not in entry.get('carriers', []):
            continue
        if args.type and args.type not in entry.get('types', []):
            continue
        labels = [taxonomy['carriers'][key] for key in entry.get('carriers', [])]
        labels += [taxonomy['types'][key] for key in entry.get('types', [])]
        groups = [
            (3, [entry['id'], entry['title']]),
            (2, [*entry.get('tags', []), *labels, *entry.get('carriers', []), *entry.get('types', []), entry.get('type', '')]),
            (1.5, [entry.get('summary', '')]),
            (1, entry.get('useCases', [])),
        ]
        haystacks = [(weight, ' '.join(values).casefold()) for weight, values in groups]
        score = sum(weight * (1 if len(term) > 1 else 0.3)
                    for term in terms for weight, text in haystacks if term in text)
        if terms and not score:
            continue
        results.append({**entry, 'score': score})
    results.sort(key=lambda row: (-row['score'], row['id']))
    emit({
        'schemaVersion': atlas.catalog['schemaVersion'], 'provenance': atlas.provenance(),
        'query': args.query, 'filters': {'kind': args.kind, 'carrier': args.carrier, 'type': args.type},
        'method': 'keyword', 'total': len(results), 'offset': args.offset,
        'limit': args.limit, 'hasMore': args.offset + args.limit < len(results),
        'results': results[args.offset:args.offset + args.limit],
    })


def show(atlas, args):
    bundle = atlas.bundle(args.entry_id)
    result = {**bundle, 'provenance': atlas.provenance()}
    if args.source:
        sources = []
        for record in bundle['files']:
            path = record['path']
            if re.search(r'\.(html|css|js)$', path) and not path.endswith('motion-kit.js'):
                try:
                    content = atlas.read(path).decode('utf-8')
                except UnicodeError as exc:
                    raise AtlasError(f'Source is not UTF-8: {path}') from exc
                sources.append({**record, 'content': content})
        result['source'] = sources
    emit(result)


def export(atlas, args):
    bundle = atlas.bundle(args.entry_id)
    out = Path(args.out).absolute()
    no_symlinks(out)
    out = out.resolve()
    if out.exists():
        raise AtlasError(f'Export requires a new directory; already exists: {out}')
    selected = [record for record in bundle['files']
                if not args.code_only or PurePosixPath(record['path']).suffix.lower() in CODE_EXTENSIONS]
    not_downloaded = [{'path': record['path'], 'bytes': record['bytes']}
                      for record in bundle['files'] if record not in selected]
    if any(record['path'].casefold() == 'atlas-export.json' for record in selected):
        raise AtlasError('Source manifest conflicts with export metadata')
    metadata = {
        'schemaVersion': 1, 'kind': bundle['kind'], 'id': args.entry_id,
        'provenance': atlas.provenance(), 'entrypoint': bundle['entrypoint'],
        'codeOnly': args.code_only, 'files': selected,
        'notDownloaded': not_downloaded, 'bundle': bundle,
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
    emit({
        'kind': bundle['kind'], 'id': args.entry_id, 'provenance': atlas.provenance(),
        'directory': str(out), 'files': len(selected), 'notDownloaded': not_downloaded,
        'entrypoint': bundle['entrypoint'],
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-root', help='Read a local Motion Atlas checkout without network access')
    parser.add_argument('--ref', help='Retrieve an explicit full 40-character Git commit for reproduction')
    parser.add_argument('--session', help="Pin this workflow's resolved commit in a JSON file in the user's working directory")
    commands = parser.add_subparsers(dest='command', required=True)
    find = commands.add_parser('search', help='Search case, pattern and material metadata by keywords')
    find.add_argument('query', nargs='?', default='')
    find.add_argument('--kind', choices=('cases', 'patterns', 'materials'), help='Entry kind filter')
    find.add_argument('--carrier', choices=('video', 'console'), help='Carrier filter')
    find.add_argument('--type', help='Exact pattern type filter from the catalog taxonomy')
    find.add_argument('--limit', type=int, default=5)
    find.add_argument('--offset', type=int, default=0, help='Skip this many ranked results; continue until hasMore is false')
    detail = commands.add_parser('show', help='Read a case, pattern or material bundle and optionally full source')
    detail.add_argument('entry_id')
    detail.add_argument('--source', action='store_true')
    save = commands.add_parser('export', help='Download a case, pattern or material into a new directory')
    save.add_argument('entry_id')
    save.add_argument('--out', required=True)
    save.add_argument('--code-only', action='store_true', help='Download only code/text extensions and list other files in notDownloaded')
    commands.add_parser('info', help='Report the active upstream version and directory counts')
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
        if args.command == 'search':
            search(atlas, args)
        elif args.command == 'show':
            show(atlas, args)
        elif args.command == 'export':
            export(atlas, args)
        else:
            result = {
                'provenance': atlas.provenance(), 'caseCount': len(atlas.catalog['cases']),
                'patternCount': len(atlas.catalog['patterns']), 'materialCount': len(atlas.catalog['materials']),
            }
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
