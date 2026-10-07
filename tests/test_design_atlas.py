import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / 'skills/design-atlas/scripts/atlas.py'
SPEC = importlib.util.spec_from_file_location('design_atlas_helper', SCRIPT)
atlas = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(atlas)
REPOSITORY = 'MIBXR/design-atlas'
REF_A, REF_B, REF_C = '1' * 40, '2' * 40, '3' * 40


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def make_version(ref, ids):
    files, entries = {}, []
    for case_id in ids:
        document_path = 'research/' + case_id + '.md'
        source_path = 'demos/' + case_id + '/index.html'
        asset_path = 'demos/' + case_id + '/assets/image.png'
        document = ('original context 中文 ' + ref).encode('utf-8')
        source = ('<h1>source ' + case_id + ' at ' + ref + '</h1>\n').encode('utf-8')
        records = []
        for path, role, data in [(document_path, 'context', document), (source_path, 'source', source), (asset_path, 'asset', b'\x89PNG\r\nfixture')]:
            files[path] = data
            records.append({'path': path, 'role': role, 'sha256': digest(data), 'bytes': len(data)})
        entry = {'id': case_id, 'title': case_id, 'category': '产品', 'tags': ['深色'], 'summary': 'workflow case', 'useCases': ['真实产品'], 'avoid': ['only pictures'], 'demo': source_path}
        bundle = {
            'schemaVersion': 1, 'id': case_id, 'entry': entry,
            'documents': [{'path': document_path, 'role': 'research', 'content': document.decode('utf-8'), 'sha256': digest(document), 'bytes': len(document)}],
            'files': records,
            'webNotes': {'format': 'text/html', 'renderer': 'atlas.js', 'content': '<section>说明 ' + ref + '</section>'},
        }
        bundle_path = 'agent/cases/' + case_id + '.json'
        files[bundle_path] = encode(bundle)
        entries.append({**entry, 'paths': {'bundle': bundle_path, 'preview': asset_path, 'demo': source_path, 'entry': 'entries/' + case_id + '.json'}, 'bundleSha256': digest(files[bundle_path])})
    catalog = {'schemaVersion': 1, 'repository': 'https://github.com/' + REPOSITORY, 'entryCount': len(entries), 'entries': entries}
    version_text = ''.join(e['id'] + ':' + e['bundleSha256'] + '\n' for e in sorted(entries, key=lambda e: e['id']))
    catalog['contentVersion'] = digest(version_text.encode('utf-8'))
    files['agent/catalog.json'] = encode(catalog)
    return files


def args(session=None, command='search', ref=None):
    return argparse.Namespace(ref=ref, local_root=None, session=str(session) if session else None, command=command)


def capture_json(action):
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        action()
    return json.loads(capture.getvalue())


class DesignAtlasTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='design-atlas-test-')
        self.addCleanup(temporary.cleanup)
        self.scratch = Path(temporary.name)
        self.session = self.scratch / 'atlas-session.json'
        self.versions = {
            REF_A: make_version(REF_A, ['old-style']),
            REF_B: make_version(REF_B, ['old-style', 'new-style']),
        }
        self.latest = REF_A
        self.api_failure = False
        self.bad_catalog = False
        self.requests = []
        network = patch.object(atlas.urllib.request, 'urlopen', self.respond)
        network.start()
        self.addCleanup(network.stop)

    def respond(self, request, timeout=None):
        url = request.full_url
        self.requests.append(url)
        api = 'https://api.github.com/repos/' + REPOSITORY
        if url.startswith(api):
            if self.api_failure:
                raise urllib.error.HTTPError(url, 503, 'temporary failure', {}, None)
            if url == api:
                return io.BytesIO(encode({'default_branch': 'trunk/design'}))
            self.assertEqual(url, api + '/commits/trunk%2Fdesign')
            return io.BytesIO(encode({'sha': self.latest}))
        prefix = 'https://raw.githubusercontent.com/' + REPOSITORY + '/'
        self.assertTrue(url.startswith(prefix), url)
        ref, path = url[len(prefix):].split('/', 1)
        data = self.versions[ref][path]
        if self.bad_catalog and path == 'agent/catalog.json':
            value = json.loads(data)
            value['contentVersion'] = '0' * 64
            data = encode(value)
        return io.BytesIO(data)

    def test_new_workflows_discover_new_cases_from_the_actual_default_branch(self):
        first = atlas.Atlas(args())
        self.assertEqual(first.default_branch, 'trunk/design')
        self.assertEqual(first.ref, REF_A)
        self.assertEqual(len(first.entries), 1)
        self.latest = REF_B
        latest = atlas.Atlas(args())
        self.assertEqual(latest.ref, REF_B)
        self.assertIn('new-style', latest.entries)
        fresh = atlas.Atlas(args(self.session))
        self.assertEqual(fresh.ref, REF_B)
        self.assertIn('new-style', fresh.entries)

    def test_session_keeps_one_version_during_iterative_search_and_retrieval(self):
        first = atlas.Atlas(args(self.session))
        state = self.session.read_bytes()
        self.assertEqual(json.loads(state)['contentVersion'], first.catalog['contentVersion'])
        self.latest = REF_B
        api_requests = len([url for url in self.requests if url.startswith('https://api.')])
        pinned = atlas.Atlas(args(self.session))
        self.assertEqual(pinned.ref, REF_A)
        self.assertNotIn('new-style', pinned.entries)
        self.assertEqual(self.session.read_bytes(), state)
        self.assertEqual(len([url for url in self.requests if url.startswith('https://api.')]), api_requests)
        shown = capture_json(lambda: atlas.show(pinned, argparse.Namespace(case_id='old-style', source=True)))
        self.assertTrue(shown['source'][0]['content'].endswith(REF_A + '</h1>\n'))

    def test_explicit_ref_reproduces_old_material_and_rejects_session_mixing(self):
        atlas.Atlas(args(self.session))
        self.latest = REF_B
        self.assertEqual(atlas.Atlas(args(ref=REF_A)).ref, REF_A)
        with self.assertRaisesRegex(atlas.AtlasError, '--ref differs'):
            atlas.Atlas(args(self.session, ref=REF_B))

    def test_refresh_exposes_new_complete_context_source_and_export(self):
        atlas.Atlas(args(self.session))
        old_state = self.session.read_bytes()
        self.latest = REF_B
        refreshed = atlas.Atlas(args(self.session, 'refresh'))
        self.assertEqual(refreshed.previous_ref, REF_A)
        self.assertEqual(refreshed.ref, REF_B)
        self.assertNotEqual(self.session.read_bytes(), old_state)
        shown = capture_json(lambda: atlas.show(refreshed, argparse.Namespace(case_id='new-style', source=True)))
        self.assertEqual(shown['entry']['id'], 'new-style')
        self.assertTrue(shown['documents'][0]['content'].endswith(REF_B))
        self.assertTrue(shown['webNotes']['content'])
        self.assertTrue(shown['source'][0]['content'].endswith(REF_B + '</h1>\n'))
        out = self.scratch / 'complete-new-case'
        capture_json(lambda: atlas.export(refreshed, argparse.Namespace(case_id='new-style', out=str(out), code_only=False)))
        metadata = json.loads((out / 'atlas-export.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['bundle']['webNotes'], shown['webNotes'])
        self.assertFalse(metadata['omitted'])
        for record in metadata['files']:
            data = (out / record['path']).read_bytes()
            self.assertEqual(len(data), record['bytes'])
            self.assertEqual(digest(data), record['sha256'])

    def test_pagination_can_visit_more_than_one_hundred_cases_in_one_category(self):
        self.versions[REF_C] = make_version(REF_C, ['case-' + str(index).zfill(3) for index in range(105)])
        self.latest = REF_C
        catalog = atlas.Atlas(args(self.session))
        pages = [capture_json(lambda offset=offset: atlas.search(catalog, argparse.Namespace(query='', category='产品', limit=100, offset=offset))) for offset in [0, 100]]
        self.assertEqual(pages[0]['total'], 105)
        self.assertTrue(pages[0]['hasMore'])
        self.assertFalse(pages[1]['hasMore'])
        self.assertEqual([len(page['results']) for page in pages], [100, 5])
        self.assertEqual(len({entry['id'] for page in pages for entry in page['results']}), 105)

    def test_invalid_catalog_or_failed_atomic_refresh_preserves_the_old_session(self):
        atlas.Atlas(args(self.session))
        state = self.session.read_bytes()
        self.latest = REF_B
        self.bad_catalog = True
        with self.assertRaisesRegex(atlas.AtlasError, 'contentVersion differs'):
            atlas.Atlas(args(self.session, 'refresh'))
        self.assertEqual(self.session.read_bytes(), state)
        self.bad_catalog = False
        with patch.object(atlas.os, 'replace', side_effect=OSError('atomic replace denied')):
            with self.assertRaisesRegex(OSError, 'atomic replace denied'):
                atlas.Atlas(args(self.session, 'refresh'))
        self.assertEqual(self.session.read_bytes(), state)
        self.assertFalse(list(self.scratch.glob('.atlas-session-*.tmp')))

    def test_resolution_failure_is_explicit_and_does_not_fall_back(self):
        atlas.Atlas(args(self.session))
        state = self.session.read_bytes()
        self.api_failure = True
        with self.assertRaisesRegex(atlas.AtlasError, 'Cannot resolve the latest'):
            atlas.Atlas(args())
        with self.assertRaisesRegex(atlas.AtlasError, 'Cannot resolve the latest'):
            atlas.Atlas(args(self.session, 'refresh'))
        self.assertEqual(self.session.read_bytes(), state)
        self.assertEqual(atlas.Atlas(args(self.session)).ref, REF_A)
        self.assertEqual(atlas.Atlas(args(ref=REF_A)).ref, REF_A)

    def test_session_identity_and_catalog_digest_are_checked(self):
        atlas.Atlas(args(self.session))
        valid = json.loads(self.session.read_bytes())
        for key, value, message in [('contentVersion', '0' * 64, 'Session catalog contentVersion differs'), ('repository', 'wrong/repository', 'Session repository or schema'), ('schemaVersion', 2, 'Session repository or schema')]:
            with self.subTest(field=key):
                self.session.write_bytes(encode({**valid, key: value}))
                with self.assertRaisesRegex(atlas.AtlasError, message):
                    atlas.Atlas(args(self.session))

    def test_sessions_are_kept_outside_the_installed_skill(self):
        forbidden = atlas.SKILL_ROOT / 'forbidden-session.json'
        with self.assertRaisesRegex(atlas.AtlasError, 'outside the installed skill'):
            atlas.Atlas(args(forbidden))
        self.assertFalse(forbidden.exists())


if __name__ == '__main__':
    unittest.main()
