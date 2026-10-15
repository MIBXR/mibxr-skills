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
SCRIPT = REPO_ROOT / 'skills/motion-atlas/scripts/atlas.py'
SPEC = importlib.util.spec_from_file_location('motion_atlas_helper', SCRIPT)
atlas = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(atlas)
REPOSITORY = 'MIBXR/motion-atlas'
REF_A, REF_B, REF_C = 'a' * 40, 'b' * 40, 'c' * 40
TAXONOMY = {
    'carriers': {'video': '影像视频', 'console': '交互操作台', 'showcase': '交互展示台'},
    'sources': {'reference': '用户提供的参考', 'game': '游戏界面转译', 'original': '原创设计语言'},
    'types': {'transition': '转场', 'rhythm': '节奏与时序', 'hud': '信息层 HUD', 'feedback': '交互反馈'},
    'evidence': {'observed': '逐帧/源码实测', 'adapted': '本地转译', 'inferred': '公开资料推断·待核验', 'original': '原创设计'},
    'roles': {'foundation': '骨架', 'support': '支撑', 'accent': '点睛'},
}


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def seal(files):
    """Recompute bundle hashes and the catalog contentVersion like scripts/lib/catalog.mjs."""
    catalog = json.loads(files['agent/catalog.json'])
    for row in [*catalog['cases'], *catalog['patterns']]:
        row['bundleSha256'] = digest(files[row['bundle']])
    lines = sorted(f"{row['bundle']}:{row['bundleSha256']}" for row in [*catalog['cases'], *catalog['patterns']])
    catalog['contentVersion'] = digest('\n'.join(lines).encode('utf-8'))
    catalog['counts'] = {'cases': len(catalog['cases']), 'patterns': len(catalog['patterns'])}
    files['agent/catalog.json'] = encode(catalog)
    return files


def make_version(ref, case_ids, pattern_count=2):
    files, cases, patterns = {}, [], []
    pattern_ids = ['wipe-' + str(n).zfill(3) for n in range(pattern_count)]
    for index, case_id in enumerate(case_ids):
        demo_dir = 'demos/cases/' + case_id
        manifest = []
        for name, data in [('index.html', '<h1>' + case_id + ' at ' + ref + '</h1>\n'), ('config.js', 'window.CONFIG = {};\n'), ('motion-kit.js', '/* kit */\n')]:
            path = demo_dir + '/' + name
            files[path] = data.encode('utf-8')
            manifest.append(path)
        preview = 'previews/cases/' + case_id + '.jpg'
        files[preview] = b'\xff\xd8preview'
        manifest.append(preview)
        research = 'docs/research/' + case_id + '.md'
        entry = {
            'id': case_id, 'title': '案例 ' + case_id, 'summary': '地图巡礼与转场 ' + ref, 'demo': demo_dir + '/index.html',
            'carriers': ['video', 'showcase'] if index == 0 else ['console'], 'source': 'reference' if index == 0 else 'game',
            'evidence': 'observed' if index == 0 else 'inferred', 'tags': ['地图叙事'] if index == 0 else ['战斗指令'],
            'useCases': ['旅行 Vlog'], 'avoid': ['长文'], 'patternIds': pattern_ids[:1], 'timeline': True, 'research': research,
        }
        bundle_path = 'agent/cases/' + case_id + '.json'
        files[bundle_path] = encode({
            'schemaVersion': 1, 'kind': 'case', 'id': case_id, 'entry': entry,
            'documents': {'prompt': '# Prompt ' + case_id + '\n', 'research': '# 研究 ' + case_id + ' ' + ref + '\n'},
            'entrypoint': entry['demo'],
            'files': [{'path': p, 'bytes': len(files[p]), 'sha256': digest(files[p])} for p in sorted(manifest)],
        })
        cases.append({key: entry[key] for key in ('id', 'title', 'summary', 'carriers', 'source', 'evidence', 'tags', 'useCases', 'avoid', 'patternIds')}
                     | {'seekable': True, 'bundle': bundle_path, 'bundleSha256': ''})
    for index, pattern_id in enumerate(pattern_ids):
        demo = 'demos/patterns/' + pattern_id + '/index.html'
        files[demo] = ('<h1>' + pattern_id + ' ' + ref + '</h1>\n').encode('utf-8')
        preview = 'previews/patterns/' + pattern_id + '.jpg'
        files[preview] = b'\xff\xd8pattern'
        pattern = {
            'id': pattern_id, 'title': '遮罩转场 ' + str(index), 'summary': '异形遮罩吞没画面', 'demo': demo,
            'types': ['transition'] if index == 0 else ['rhythm', 'feedback'], 'carriers': ['video'],
            'composition': {'role': 'accent' if index == 0 else 'foundation', 'pairsWellWith': [p for p in pattern_ids if p != pattern_id][:1], 'conflicts': []},
            'sources': [{'caseId': case_ids[0], 'evidence': 'observed'}],
        }
        bundle_path = 'agent/patterns/' + pattern_id + '.json'
        files[bundle_path] = encode({
            'schemaVersion': 1, 'kind': 'pattern', 'id': pattern_id, 'pattern': pattern,
            'sourceCases': [{'caseId': case_ids[0], 'bundle': 'agent/cases/' + case_ids[0] + '.json'}],
            'documents': {'prompt': '# Prompt ' + pattern_id + '\n'}, 'entrypoint': demo,
            'files': [{'path': p, 'bytes': len(files[p]), 'sha256': digest(files[p])} for p in (demo, preview)],
        })
        patterns.append({'id': pattern_id, 'title': pattern['title'], 'summary': pattern['summary'], 'types': pattern['types'], 'carriers': pattern['carriers'],
                         'role': pattern['composition']['role'], 'sourceCases': [case_ids[0]], 'pairsWellWith': pattern['composition']['pairsWellWith'],
                         'bundle': bundle_path, 'bundleSha256': ''})
    files['agent/catalog.json'] = encode({'schemaVersion': 1, 'name': 'Motion Atlas', 'contentVersion': '', 'taxonomy': TAXONOMY,
                                          'protocol': {'seek': 'window.__motion'}, 'counts': {}, 'cases': cases, 'patterns': patterns})
    return seal(files)


def args(session=None, command='search', ref=None, local_root=None):
    return argparse.Namespace(ref=ref, local_root=str(local_root) if local_root else None, session=str(session) if session else None, command=command)


def search_args(query='', limit=100, offset=0, **filters):
    return argparse.Namespace(query=query, limit=limit, offset=offset, carrier=filters.get('carrier'), evidence=filters.get('evidence'),
                              origin=filters.get('origin'), seekable=filters.get('seekable', False))


def pattern_args(query='', limit=100, offset=0, **filters):
    return argparse.Namespace(query=query, limit=limit, offset=offset, type=filters.get('type'), carrier=filters.get('carrier'),
                              role=filters.get('role'), case=filters.get('case'))


def capture_json(action):
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        action()
    return json.loads(capture.getvalue())


class MotionAtlasTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='motion-atlas-test-')
        self.addCleanup(temporary.cleanup)
        self.scratch = Path(temporary.name)
        self.session = self.scratch / 'motion-session.json'
        self.versions = {REF_A: make_version(REF_A, ['map-trip']), REF_B: make_version(REF_B, ['map-trip', 'battle-menu'], pattern_count=3)}
        self.latest = REF_A
        self.api_failure = False
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
                return io.BytesIO(encode({'default_branch': 'main'}))
            self.assertEqual(url, api + '/commits/main')
            return io.BytesIO(encode({'sha': self.latest}))
        prefix = 'https://raw.githubusercontent.com/' + REPOSITORY + '/'
        self.assertTrue(url.startswith(prefix), url)
        ref, path = url[len(prefix):].split('/', 1)
        if path not in self.versions[ref]:
            raise urllib.error.HTTPError(url, 404, 'not found', {}, None)
        return io.BytesIO(self.versions[ref][path])

    def test_session_pins_one_version_until_explicit_refresh(self):
        first = atlas.Atlas(args(self.session))
        self.assertEqual((first.ref, first.default_branch, len(first.cases)), (REF_A, 'main', 1))
        state = self.session.read_bytes()
        self.latest = REF_B
        pinned = atlas.Atlas(args(self.session, 'show'))
        self.assertEqual(pinned.ref, REF_A)
        self.assertNotIn('battle-menu', pinned.cases)
        self.assertEqual(self.session.read_bytes(), state)
        refreshed = atlas.Atlas(args(self.session, 'refresh'))
        self.assertEqual((refreshed.previous_ref, refreshed.ref), (REF_A, REF_B))
        self.assertIn('battle-menu', refreshed.cases)
        self.assertEqual(json.loads(self.session.read_bytes())['contentVersion'], refreshed.catalog['contentVersion'])

    def test_explicit_ref_reproduces_and_rejects_session_mixing(self):
        atlas.Atlas(args(self.session))
        self.latest = REF_B
        self.assertEqual(atlas.Atlas(args(ref=REF_A)).ref, REF_A)
        with self.assertRaisesRegex(atlas.AtlasError, '--ref differs'):
            atlas.Atlas(args(self.session, ref=REF_B))

    def test_resolution_failure_is_explicit_and_keeps_the_session(self):
        atlas.Atlas(args(self.session))
        state = self.session.read_bytes()
        self.api_failure = True
        with self.assertRaisesRegex(atlas.AtlasError, 'Cannot resolve the latest'):
            atlas.Atlas(args())
        with self.assertRaisesRegex(atlas.AtlasError, 'Cannot resolve the latest'):
            atlas.Atlas(args(self.session, 'refresh'))
        self.assertEqual(self.session.read_bytes(), state)
        self.assertEqual(atlas.Atlas(args(self.session)).ref, REF_A)

    def test_sessions_are_kept_outside_the_installed_skill(self):
        forbidden = atlas.SKILL_ROOT / 'forbidden-session.json'
        with self.assertRaisesRegex(atlas.AtlasError, 'outside the installed skill'):
            atlas.Atlas(args(forbidden))
        self.assertFalse(forbidden.exists())

    def test_catalog_integrity_is_checked(self):
        self.latest = REF_C
        broken = make_version(REF_C, ['map-trip'])
        catalog = json.loads(broken['agent/catalog.json'])
        catalog['contentVersion'] = '0' * 64
        broken['agent/catalog.json'] = encode(catalog)
        self.versions[REF_C] = broken
        with self.assertRaisesRegex(atlas.AtlasError, 'contentVersion differs'):
            atlas.Atlas(args())
        for mutate, message in [
            (lambda c: c['cases'][0].update(carriers=['radio']), 'invalid carriers'),
            (lambda c: c['patterns'][0].update(sourceCases=['missing-case']), 'unknown source case'),
            (lambda c: c['cases'][0].update(bundle='agent/cases/../x.json'), 'bundle path differs'),
            (lambda c: c.update(counts={'cases': 9, 'patterns': 9}), 'counts differ'),
        ]:
            with self.subTest(message=message):
                files = make_version(REF_C, ['map-trip'])
                catalog = json.loads(files['agent/catalog.json'])
                mutate(catalog)
                files['agent/catalog.json'] = encode(catalog)
                self.versions[REF_C] = files
                with self.assertRaisesRegex(atlas.AtlasError, message):
                    atlas.Atlas(args())

    def test_case_search_filters_and_pages(self):
        self.latest = REF_B
        catalog = atlas.Atlas(args(self.session))
        everything = capture_json(lambda: atlas.search(catalog, search_args()))
        self.assertEqual(everything['total'], 2)
        games = capture_json(lambda: atlas.search(catalog, search_args(origin='game')))
        self.assertEqual([row['id'] for row in games['results']], ['battle-menu'])
        observed = capture_json(lambda: atlas.search(catalog, search_args('地图叙事', carrier='video', evidence='observed')))
        self.assertEqual([row['id'] for row in observed['results']], ['map-trip'])
        self.assertIn('tags', observed['results'][0]['matches'][0]['fields'])
        self.assertEqual(observed['results'][0]['evidenceLabel'], '逐帧/源码实测')
        first = capture_json(lambda: atlas.search(catalog, search_args(limit=1)))
        second = capture_json(lambda: atlas.search(catalog, search_args(limit=1, offset=1)))
        self.assertTrue(first['hasMore'])
        self.assertFalse(second['hasMore'])
        self.assertNotEqual(first['results'][0]['id'], second['results'][0]['id'])
        with self.assertRaisesRegex(atlas.AtlasError, "Unknown --carrier 'radio'"):
            atlas.search(catalog, search_args(carrier='radio'))

    def test_pattern_search_filters_by_type_role_and_case(self):
        self.latest = REF_B
        catalog = atlas.Atlas(args(self.session))
        transitions = capture_json(lambda: atlas.pattern_search(catalog, pattern_args(type='transition')))
        self.assertEqual([row['id'] for row in transitions['results']], ['wipe-000'])
        foundations = capture_json(lambda: atlas.pattern_search(catalog, pattern_args(role='foundation', case='map-trip')))
        self.assertEqual([row['id'] for row in foundations['results']], ['wipe-001', 'wipe-002'])
        labelled = capture_json(lambda: atlas.pattern_search(catalog, pattern_args('节奏与时序')))
        self.assertEqual({row['id'] for row in labelled['results']}, {'wipe-001', 'wipe-002'})
        with self.assertRaisesRegex(atlas.AtlasError, 'Unknown case ID'):
            atlas.pattern_search(catalog, pattern_args(case='missing'))

    def test_show_returns_verified_source_and_documents(self):
        catalog = atlas.Atlas(args(self.session))
        shown = capture_json(lambda: atlas.show(catalog, argparse.Namespace(case_id='map-trip', source=True)))
        self.assertEqual(shown['entrypoint'], 'demos/cases/map-trip/index.html')
        self.assertEqual({record['role'] for record in shown['files']}, {'source', 'preview'})
        self.assertEqual(len(shown['source']), 3)
        self.assertTrue(any(record['content'].endswith(REF_A + '</h1>\n') for record in shown['source']))
        self.assertTrue(shown['documents']['research'].startswith('# 研究'))
        pattern = capture_json(lambda: atlas.pattern_show(catalog, argparse.Namespace(pattern_id='wipe-000', source=True)))
        self.assertEqual([row['id'] for row in pattern['sourceCaseSummaries']], ['map-trip'])
        self.assertEqual([record['path'] for record in pattern['source']], ['demos/patterns/wipe-000/index.html'])

    def test_tampered_bundle_or_source_is_rejected(self):
        catalog = atlas.Atlas(args(self.session))
        files = self.versions[REF_A]
        original = files['demos/cases/map-trip/index.html']
        files['demos/cases/map-trip/index.html'] = b'<h1>changed</h1>\n'
        with self.assertRaisesRegex(atlas.AtlasError, 'Byte length mismatch|SHA-256 mismatch'):
            atlas.show(catalog, argparse.Namespace(case_id='map-trip', source=True))
        files['demos/cases/map-trip/index.html'] = original
        files['agent/cases/map-trip.json'] += b' '
        with self.assertRaisesRegex(atlas.AtlasError, 'bundle SHA-256 mismatch'):
            atlas.show(catalog, argparse.Namespace(case_id='map-trip', source=False))

    def test_unsafe_paths_in_a_resealed_bundle_are_rejected(self):
        self.latest = REF_C
        files = make_version(REF_C, ['map-trip'])
        bundle = json.loads(files['agent/cases/map-trip.json'])
        bundle['files'].append({'path': '../outside.js', 'bytes': 1, 'sha256': '0' * 64})
        files['agent/cases/map-trip.json'] = encode(bundle)
        self.versions[REF_C] = seal(files)
        catalog = atlas.Atlas(args())
        with self.assertRaisesRegex(atlas.AtlasError, 'Unsafe repository path'):
            atlas.show(catalog, argparse.Namespace(case_id='map-trip', source=False))

    def test_export_writes_verified_demo_prompt_and_research(self):
        catalog = atlas.Atlas(args(self.session))
        out = self.scratch / 'exported-case'
        result = capture_json(lambda: atlas.export(catalog, argparse.Namespace(case_id='map-trip', out=str(out), code_only=False)))
        self.assertEqual(result['files'], 4)
        self.assertFalse(result['omitted'])
        metadata = json.loads((out / 'atlas-export.json').read_text(encoding='utf-8'))
        for record in metadata['files']:
            data = (out / record['path']).read_bytes()
            self.assertEqual((len(data), digest(data)), (record['bytes'], record['sha256']))
        self.assertEqual((out / 'prompts/cases/map-trip.md').read_text(encoding='utf-8'), '# Prompt map-trip\n')
        self.assertTrue((out / 'docs/research/map-trip.md').exists())
        with self.assertRaisesRegex(atlas.AtlasError, 'requires a new directory'):
            atlas.export(catalog, argparse.Namespace(case_id='map-trip', out=str(out), code_only=False))

    def test_code_only_pattern_export_lists_omitted_previews(self):
        catalog = atlas.Atlas(args(self.session))
        out = self.scratch / 'exported-pattern'
        result = capture_json(lambda: atlas.pattern_export(catalog, argparse.Namespace(pattern_id='wipe-000', out=str(out), code_only=True)))
        self.assertEqual(result['omitted'], ['previews/patterns/wipe-000.jpg'])
        self.assertFalse((out / 'previews').exists())
        metadata = json.loads((out / 'atlas-export.json').read_text(encoding='utf-8'))
        self.assertTrue(metadata['filesNotDownloaded'][0]['url'].startswith('https://raw.githubusercontent.com/' + REPOSITORY + '/' + REF_A + '/'))

    def test_failed_export_removes_the_partial_directory(self):
        catalog = atlas.Atlas(args(self.session))
        self.versions[REF_A]['demos/cases/map-trip/motion-kit.js'] = b'tampered\n'
        out = self.scratch / 'partial'
        with self.assertRaises(atlas.AtlasError):
            atlas.export(catalog, argparse.Namespace(case_id='map-trip', out=str(out), code_only=False))
        self.assertFalse(out.exists())

    def test_local_root_reads_a_checkout_offline(self):
        root = self.scratch / 'checkout'
        for path, data in self.versions[REF_B].items():
            target = root.joinpath(*path.split('/'))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.requests.clear()
        catalog = atlas.Atlas(args(command='show', local_root=root))
        self.assertEqual(catalog.resolution, 'local')
        shown = capture_json(lambda: atlas.show(catalog, argparse.Namespace(case_id='battle-menu', source=True)))
        self.assertTrue(any(REF_B in record['content'] for record in shown['source']))
        self.assertEqual(self.requests, [])


if __name__ == '__main__':
    unittest.main()
