import argparse
import copy
import json
import unittest
from unittest.mock import patch

import test_design_atlas as fixtures
from test_design_atlas import REF_A, REF_B, REF_C, REPOSITORY, args, atlas, capture_json, digest, encode, make_version


def reseal(files):
    catalog = json.loads(files['agent/catalog.json'])
    for entry in catalog['entries']:
        entry['bundleSha256'] = digest(files[entry['paths']['bundle']])
    patterns = json.loads(files['agent/patterns.json'])
    for pattern in patterns['patterns']:
        pattern['bundleSha256'] = digest(files[pattern['paths']['bundle']])
    patterns['contentVersion'] = digest(''.join(f"{row['id']}:{row['bundleSha256']}\n" for row in sorted(patterns['patterns'], key=lambda row: row['id'])).encode('utf-8'))
    files['agent/patterns.json'] = encode(patterns)
    catalog['patterns'] = {'path': 'agent/patterns.json', 'sha256': digest(files['agent/patterns.json']), 'bytes': len(files['agent/patterns.json']), 'patternCount': len(patterns['patterns']), 'contentVersion': patterns['contentVersion']}
    version = ''.join(f"{row['id']}:{row['bundleSha256']}\n" for row in sorted(catalog['entries'], key=lambda row: row['id'])) + f"patterns:{patterns['contentVersion']}\n"
    catalog['contentVersion'] = digest(version.encode('utf-8'))
    files['agent/catalog.json'] = encode(catalog)
    return files


def with_patterns(files, count=2):
    catalog = json.loads(files['agent/catalog.json'])
    rows = []
    for number in range(count):
        pattern_id = 'focus-' + str(number).zfill(3)
        sources = catalog['entries'] if number == 0 else catalog['entries'][-1:]
        source_files = [entry['paths']['demo'] for entry in sources]
        source_files += ['research/' + entry['id'] + '.md' for entry in sources]
        pattern = {
            'id': pattern_id, 'title': '焦点 Focus ' + str(number), 'category': '交互反馈',
            'experienceTypes': ['visual', 'micro-motion'] if number == 0 else ['page-motion'],
            'summary': '首屏悬停聚焦', 'mechanism': 'Opacity focus for the active card',
            'trigger': 'pointer hover / keyboard focus', 'effect': 'Keep attention on one item',
            'useCases': ['产品入口', 'portfolio'], 'avoid': ['密集长文'],
            'constraints': ['保留文字对比度'], 'prompt': 'Create a keyboard accessible focus effect',
            'composition': {'role': 'accent', 'notes': 'Use after the page hierarchy is established', 'pairsWellWith': [], 'conflicts': []},
            'accessibility': {'keyboard': 'focus-visible mirrors hover', 'reducedMotion': 'Use an instant opacity update'},
            'parameters': [{'name': 'duration', 'value': '160ms', 'note': 'Short feedback'}],
            'sources': [{'caseId': entry['id'], 'locator': 'hero', 'observation': 'Focus dims siblings', 'evidence': 'observed'} for entry in sources],
            'sourceFiles': source_files,
        }
        path = 'agent/patterns/' + pattern_id + '.json'
        bundle = {'schemaVersion': 1, 'id': pattern_id, 'pattern': pattern, 'sourceCases': [{'id': entry['id'], 'title': entry['title'], 'paths': {key: entry['paths'][key] for key in ('bundle', 'demo')}, 'bundleSha256': entry['bundleSha256']} for entry in sources]}
        files[path] = encode(bundle)
        rows.append({**pattern, 'paths': {'bundle': path}, 'bundleSha256': digest(files[path])})
    files['agent/patterns.json'] = encode({'schemaVersion': 1, 'repository': 'https://github.com/' + REPOSITORY, 'contentVersion': '', 'patternCount': count, 'patterns': rows})
    return reseal(files)


def search_args(query='', category=None, case=None, limit=100, offset=0, experience_type=None):
    return argparse.Namespace(query=query, category=category, case=case, limit=limit, offset=offset, type=experience_type)


class DesignPatternTests(unittest.TestCase):
    def setUp(self):
        fixtures.DesignAtlasTests.setUp(self)
        self.versions[REF_B] = with_patterns(make_version(REF_B, ['old-style', 'new-style']))
        self.latest = REF_B

    respond = fixtures.DesignAtlasTests.respond

    def test_pattern_growth_and_pagination_are_not_limited_to_one_hundred(self):
        self.versions[REF_C] = with_patterns(make_version(REF_C, ['old-style', 'new-style']), count=105)
        atlas.Atlas(args(self.session))
        self.latest = REF_C
        pinned = atlas.Atlas(args(self.session, 'pattern-search'))
        self.assertEqual(len(pinned.patterns), 2)
        updated = atlas.Atlas(args(self.session, 'refresh'))
        pages = [capture_json(lambda offset=offset: atlas.pattern_search(updated, search_args(category='交互反馈', offset=offset))) for offset in (0, 100)]
        self.assertEqual([len(page['results']) for page in pages], [100, 5])
        self.assertEqual(pages[0]['total'], 105)
        self.assertTrue(pages[0]['hasMore'])
        self.assertFalse(pages[1]['hasMore'])
        self.assertEqual(len({row['id'] for page in pages for row in page['results']}), 105)
        self.assertEqual(pages[0]['provenance']['ref'], REF_C)

    def test_patterns_search_chinese_english_and_source_cases(self):
        active = atlas.Atlas(args())
        for query in ('焦点', 'FOCUS', 'Opacity', 'portfolio', 'keyboard', 'new-style'):
            with self.subTest(query=query):
                result = capture_json(lambda: atlas.pattern_search(active, search_args(query)))
                self.assertEqual(result['total'], 2)
                self.assertTrue(result['results'][0]['matches'])
        result = capture_json(lambda: atlas.pattern_search(active, search_args(case='old-style')))
        self.assertEqual([row['id'] for row in result['results']], ['focus-000'])
        self.assertEqual(result['results'][0]['sourceCases'][0]['id'], 'new-style')
        self.assertEqual(capture_json(lambda: atlas.pattern_search(active, search_args(category='滚动叙事')))['total'], 0)
        self.assertEqual(capture_json(lambda: atlas.pattern_search(active, search_args('no-match')))['total'], 0)

    def test_pattern_show_keeps_full_metadata_context_and_verified_source(self):
        active = atlas.Atlas(args(self.session, 'pattern-show'))
        shown = capture_json(lambda: atlas.pattern_show(active, argparse.Namespace(pattern_id='focus-000', source=True)))
        self.assertEqual(shown['provenance']['ref'], REF_B)
        self.assertEqual(shown['pattern']['composition']['role'], 'accent')
        self.assertEqual(shown['pattern']['experienceTypes'], ['visual', 'micro-motion'])
        self.assertTrue(shown['pattern']['accessibility']['reducedMotion'])
        self.assertTrue(shown['pattern']['prompt'])
        self.assertEqual({case['id'] for case in shown['sourceCaseBundles']}, {'old-style', 'new-style'})
        self.assertEqual(len(shown['source']), 2)
        for case in shown['sourceCaseBundles']:
            self.assertTrue(case['documents'][0]['content'].endswith(REF_B))
            self.assertTrue(case['webNotes']['content'])
        for source in shown['source']:
            self.assertEqual(digest(source['content'].encode('utf-8')), source['sha256'])

    def test_relevant_source_is_scoped_while_exports_keep_runtime_dependencies(self):
        files = make_version(REF_B, ['old-style'])
        source_path = 'demos/old-style/runtime.js'
        source = b'window.runtime = true;\n'
        files[source_path] = source
        case_path = 'agent/cases/old-style.json'
        case = json.loads(files[case_path])
        case['files'].append({'path': source_path, 'role': 'source', 'sha256': digest(source), 'bytes': len(source)})
        files[case_path] = encode(case)
        catalog = json.loads(files['agent/catalog.json'])
        catalog['entries'][0]['bundleSha256'] = digest(files[case_path])
        files['agent/catalog.json'] = encode(catalog)
        self.versions[REF_B] = with_patterns(files)
        active = atlas.Atlas(args())
        shown = capture_json(lambda: atlas.pattern_show(active, argparse.Namespace(pattern_id='focus-000', source=True)))
        self.assertEqual([record['path'] for record in shown['source']], ['demos/old-style/index.html'])
        out = self.scratch / 'with-runtime'
        capture_json(lambda: atlas.pattern_export(active, argparse.Namespace(pattern_id='focus-000', out=str(out), code_only=True)))
        self.assertEqual((out / source_path).read_bytes(), source)

    def test_source_case_title_and_demo_must_match_the_verified_bundle(self):
        for field, value in [('title', 'Different title'), ('demo', 'demos/old-style/other.html')]:
            with self.subTest(field=field):
                files = make_version(REF_B, ['old-style'])
                case_path = 'agent/cases/old-style.json'
                case = json.loads(files[case_path])
                case['entry'][field] = value
                files[case_path] = encode(case)
                catalog = json.loads(files['agent/catalog.json'])
                catalog['entries'][0]['bundleSha256'] = digest(files[case_path])
                files['agent/catalog.json'] = encode(catalog)
                self.versions[REF_B] = with_patterns(files)
                active = atlas.Atlas(args())
                with self.assertRaisesRegex(atlas.AtlasError, 'title or demo differs'):
                    active.pattern_bundle('focus-000')

    def test_pattern_export_downloads_related_demos_and_context_with_provenance(self):
        active = atlas.Atlas(args(self.session, 'pattern-export'))
        for code_only in (False, True):
            with self.subTest(code_only=code_only):
                out = self.scratch / ('pattern-code' if code_only else 'pattern-complete')
                result = capture_json(lambda: atlas.pattern_export(active, argparse.Namespace(pattern_id='focus-000', out=str(out), code_only=code_only)))
                metadata = json.loads((out / 'atlas-export.json').read_text(encoding='utf-8'))
                self.assertEqual(metadata['kind'], 'pattern')
                self.assertEqual(metadata['provenance']['ref'], REF_B)
                self.assertEqual(metadata['provenance']['contentVersion'], active.catalog['contentVersion'])
                self.assertEqual(metadata['sourceFiles'], metadata['bundle']['pattern']['sourceFiles'])
                self.assertEqual(metadata['bundle']['pattern']['experienceTypes'], ['visual', 'micro-motion'])
                self.assertEqual(len(metadata['sourceCaseBundles']), 2)
                self.assertEqual(len(result['entrypoints']), 2)
                self.assertEqual(len(metadata['files']), 4 if code_only else 6)
                self.assertEqual(len(metadata['omitted']), 2 if code_only else 0)
                for record in metadata['files']:
                    data = (out / record['path']).read_bytes()
                    self.assertEqual(len(data), record['bytes'])
                    self.assertEqual(digest(data), record['sha256'])
                    self.assertTrue(record['caseIds'])
                if code_only:
                    self.assertTrue(all(item['url'].startswith('https://raw.githubusercontent.com/' + REPOSITORY + '/' + REF_B + '/') for item in metadata['filesNotDownloaded']))
                with self.assertRaisesRegex(atlas.AtlasError, 'already exists'):
                    atlas.pattern_export(active, argparse.Namespace(pattern_id='focus-000', out=str(out), code_only=code_only))

    def test_pattern_only_changes_update_the_shared_session_version(self):
        active = atlas.Atlas(args(self.session))
        self.versions[REF_C] = with_patterns(copy.deepcopy(self.versions[REF_B]), count=3)
        self.latest = REF_C
        pinned = atlas.Atlas(args(self.session, 'pattern-search'))
        self.assertEqual(pinned.ref, REF_B)
        self.assertEqual(len(pinned.patterns), 2)
        self.assertEqual(pinned.catalog['contentVersion'], active.catalog['contentVersion'])
        refreshed = atlas.Atlas(args(self.session, 'refresh'))
        self.assertEqual(len(refreshed.patterns), 3)
        self.assertNotEqual(refreshed.catalog['contentVersion'], active.catalog['contentVersion'])
        self.assertEqual(refreshed.entries, active.entries)

    def test_legacy_versions_explain_how_to_access_patterns_without_breaking_cases(self):
        self.latest = REF_A
        active = atlas.Atlas(args(self.session))
        old = self.session.read_bytes()
        self.assertEqual(len(active.entries), 1)
        with self.assertRaisesRegex(atlas.AtlasError, 'no design patterns library.*refresh'):
            atlas.Atlas(args(self.session, 'pattern-search'))
        self.assertEqual(self.session.read_bytes(), old)
        with self.assertRaisesRegex(atlas.AtlasError, 'no design patterns library'):
            atlas.Atlas(args(self.scratch / 'new-pattern-session.json', 'pattern-show'))
        self.assertFalse((self.scratch / 'new-pattern-session.json').exists())

    def test_pattern_manifest_integrity_failure_preserves_old_session(self):
        self.latest = REF_A
        atlas.Atlas(args(self.session))
        old = self.session.read_bytes()
        self.latest = REF_B
        valid = copy.deepcopy(self.versions[REF_B])
        for field, value, message in [('sha256', '0' * 64, 'SHA-256 mismatch'), ('bytes', 0, 'Byte length mismatch'), ('contentVersion', '0' * 64, 'contentVersion differs'), ('patternCount', 0, 'patternCount')]:
            with self.subTest(field=field):
                self.versions[REF_B] = copy.deepcopy(valid)
                catalog = json.loads(self.versions[REF_B]['agent/catalog.json'])
                catalog['patterns'][field] = value
                self.versions[REF_B]['agent/catalog.json'] = encode(catalog)
                with self.assertRaisesRegex(atlas.AtlasError, message):
                    atlas.Atlas(args(self.session, 'refresh'))
                self.assertEqual(self.session.read_bytes(), old)

    def test_pattern_repository_schema_links_and_evidence_are_validated(self):
        valid = copy.deepcopy(self.versions[REF_B])
        changes = [
            ('repository', lambda data: data.update(repository='wrong/repo'), 'repository differs'),
            ('schema', lambda data: data.update(schemaVersion=2), 'schemaVersion'),
            ('source identity', lambda data: data['patterns'][0]['sources'][0].update(caseId='missing'), 'unknown source case'),
            ('evidence', lambda data: data['patterns'][0]['sources'][0].update(evidence='assumed'), 'source evidence'),
            ('composition links', lambda data: data['patterns'][0]['composition'].update(pairsWellWith=['missing-pattern']), 'unknown or self-referential'),
            ('source path', lambda data: data['patterns'][0].update(sourceFiles=['../escape']), 'Unsafe repository path'),
            ('bundle path', lambda data: data['patterns'][0]['paths'].update(bundle='agent/patterns/wrong.json'), 'bundle path differs'),
        ]
        for label, mutate, message in changes:
            with self.subTest(label=label):
                files = copy.deepcopy(valid)
                data = json.loads(files['agent/patterns.json'])
                mutate(data)
                files['agent/patterns.json'] = encode(data)
                catalog = json.loads(files['agent/catalog.json'])
                catalog['patterns'].update(sha256=digest(files['agent/patterns.json']), bytes=len(files['agent/patterns.json']))
                files['agent/catalog.json'] = encode(catalog)
                self.versions[REF_B] = files
                with self.assertRaisesRegex(atlas.AtlasError, message):
                    atlas.Atlas(args())

    def test_pattern_bundle_and_source_case_integrity_are_checked_at_retrieval(self):
        valid = copy.deepcopy(self.versions[REF_B])
        path = 'agent/patterns/focus-000.json'
        mutations = [
            (lambda bundle: bundle.update(id='wrong-pattern'), 'identity'),
            (lambda bundle: bundle['pattern'].update(title='changed'), 'metadata mismatch'),
            (lambda bundle: bundle['pattern'].update(experienceTypes=['sound']), 'metadata mismatch'),
            (lambda bundle: bundle['sourceCases'][0].update(id='missing'), 'source case identity'),
            (lambda bundle: bundle['sourceCases'][0].update(bundleSha256='0' * 64), 'source case metadata or SHA-256'),
            (lambda bundle: bundle['sourceCases'][0]['paths'].update(demo='demos/other/index.html'), 'source case metadata or SHA-256'),
        ]
        for mutate, message in mutations:
            with self.subTest(message=message):
                files = copy.deepcopy(valid)
                bundle = json.loads(files[path])
                mutate(bundle)
                files[path] = encode(bundle)
                self.versions[REF_B] = reseal(files)
                active = atlas.Atlas(args())
                with self.assertRaisesRegex(atlas.AtlasError, message):
                    active.pattern_bundle('focus-000')
        self.versions[REF_B] = copy.deepcopy(valid)
        active = atlas.Atlas(args())
        self.versions[REF_B][path] += b' '
        with self.assertRaisesRegex(atlas.AtlasError, 'Pattern bundle SHA-256 mismatch'):
            active.pattern_bundle('focus-000')
        self.versions[REF_B] = copy.deepcopy(valid)
        active = atlas.Atlas(args())
        self.versions[REF_B]['agent/cases/old-style.json'] += b' '
        with self.assertRaisesRegex(atlas.AtlasError, 'Bundle SHA-256 mismatch'):
            active.pattern_bundle('focus-000')

    def test_missing_source_files_and_tampered_source_fail_without_partial_export(self):
        files = self.versions[REF_B]
        path = 'agent/patterns/focus-000.json'
        bundle = json.loads(files[path])
        bundle['pattern']['sourceFiles'].append('demos/old-style/missing.js')
        files[path] = encode(bundle)
        catalog = json.loads(files['agent/patterns.json'])
        catalog['patterns'][0]['sourceFiles'] = bundle['pattern']['sourceFiles']
        files['agent/patterns.json'] = encode(catalog)
        reseal(files)
        active = atlas.Atlas(args())
        with self.assertRaisesRegex(atlas.AtlasError, 'absent from verified source case manifests'):
            active.pattern_bundle('focus-000')
        self.versions[REF_B] = with_patterns(make_version(REF_B, ['old-style', 'new-style']))
        active = atlas.Atlas(args())
        self.versions[REF_B]['demos/new-style/index.html'] = b'tampered source'
        with self.assertRaisesRegex(atlas.AtlasError, 'mismatch'):
            atlas.pattern_show(active, argparse.Namespace(pattern_id='focus-000', source=True))
        out = self.scratch / 'failed-export'
        with self.assertRaisesRegex(atlas.AtlasError, 'mismatch'):
            atlas.pattern_export(active, argparse.Namespace(pattern_id='focus-000', out=str(out), code_only=False))
        self.assertFalse(out.exists())

    def test_pattern_commands_accept_the_shared_session_and_filters(self):
        with patch.object(atlas.sys, 'argv', ['atlas.py', '--session', str(self.session), 'pattern-search', '焦点', '--case', 'old-style', '--category', '交互反馈', '--type', 'micro-motion', '--limit', '1', '--offset', '0']):
            capture = capture_json(lambda: self.assertEqual(atlas.main(), 0))
        self.assertEqual(capture['total'], 1)
        self.assertEqual(capture['provenance']['ref'], REF_B)
        self.assertEqual(capture['filters']['type'], 'micro-motion')

    def test_experience_filter_matches_multi_type_patterns_without_source_inheritance(self):
        active = atlas.Atlas(args())
        for experience_type, expected in [('visual', ['focus-000']), ('micro-motion', ['focus-000']), ('page-motion', ['focus-001']), ('sound', []), ('structure', [])]:
            with self.subTest(experience_type=experience_type):
                result = capture_json(lambda: atlas.pattern_search(active, search_args(experience_type=experience_type)))
                self.assertEqual([row['id'] for row in result['results']], expected)
                for row in result['results']:
                    self.assertIn(experience_type, row['experienceTypes'])
        filtered = capture_json(lambda: atlas.pattern_search(active, search_args(case='old-style', experience_type='page-motion')))
        self.assertEqual(filtered['total'], 0)
        keyword = capture_json(lambda: atlas.pattern_search(active, search_args(query='micro-motion')))
        self.assertEqual([row['id'] for row in keyword['results']], ['focus-000'])
        self.assertIn('experienceTypes', keyword['results'][0]['matches'][0]['fields'])

    def test_unclassified_pinned_patterns_remain_readable_until_explicit_refresh(self):
        files = copy.deepcopy(self.versions[REF_B])
        catalog = json.loads(files['agent/patterns.json'])
        for row in catalog['patterns']:
            del row['experienceTypes']
            bundle = json.loads(files[row['paths']['bundle']])
            del bundle['pattern']['experienceTypes']
            files[row['paths']['bundle']] = encode(bundle)
        files['agent/patterns.json'] = encode(catalog)
        self.versions[REF_B] = reseal(files)
        old = atlas.Atlas(args(self.session))
        state = self.session.read_bytes()
        searched = capture_json(lambda: atlas.pattern_search(old, search_args()))
        self.assertTrue(all(row['experienceTypes'] == [] for row in searched['results']))
        shown = capture_json(lambda: atlas.pattern_show(old, argparse.Namespace(pattern_id='focus-000', source=True)))
        self.assertNotIn('experienceTypes', shown['pattern'])
        with self.assertRaisesRegex(atlas.AtlasError, 'no experience type classifications.*refresh'):
            atlas.pattern_search(old, search_args(experience_type='micro-motion'))
        self.versions[REF_C] = with_patterns(make_version(REF_C, ['old-style', 'new-style']))
        self.latest = REF_C
        pinned = atlas.Atlas(args(self.session))
        self.assertEqual(pinned.ref, REF_B)
        self.assertEqual(self.session.read_bytes(), state)
        updated = atlas.Atlas(args(self.session, 'refresh'))
        searched = capture_json(lambda: atlas.pattern_search(updated, search_args(experience_type='micro-motion')))
        self.assertEqual([row['id'] for row in searched['results']], ['focus-000'])
        self.assertEqual(searched['provenance']['ref'], REF_C)

    def test_invalid_experience_classifications_preserve_the_pinned_session(self):
        self.latest = REF_A
        atlas.Atlas(args(self.session))
        state = self.session.read_bytes()
        self.latest = REF_B
        valid = copy.deepcopy(self.versions[REF_B])
        for value in ([], 'visual', ['unknown'], ['visual', 'visual'], [None]):
            with self.subTest(value=value):
                files = copy.deepcopy(valid)
                catalog = json.loads(files['agent/patterns.json'])
                catalog['patterns'][0]['experienceTypes'] = value
                files['agent/patterns.json'] = encode(catalog)
                self.versions[REF_B] = reseal(files)
                with self.assertRaisesRegex(atlas.AtlasError, 'invalid experienceTypes'):
                    atlas.Atlas(args(self.session, 'refresh'))
                self.assertEqual(self.session.read_bytes(), state)
