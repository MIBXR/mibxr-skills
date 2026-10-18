import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'skills/design-atlas/scripts/atlas.py'
SPEC = importlib.util.spec_from_file_location('atlas', SCRIPT)
atlas = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(atlas)


class DesignAtlasTests(unittest.TestCase):
    def test_session_stays_on_its_commit_until_refresh(self):
        with tempfile.TemporaryDirectory() as temporary:
            session = Path(temporary) / 'session.json'
            args = SimpleNamespace(ref=None, local_root=None, session=str(session), command='search')
            catalog = json.dumps({'schemaVersion': 1, 'entries': []}).encode()
            with patch.object(atlas.Atlas, 'read', return_value=catalog), patch.object(atlas.Atlas, 'resolve_latest', return_value=('1' * 40, 'main')) as resolve:
                self.assertEqual(atlas.Atlas(args).ref, '1' * 40)
                state = json.loads(session.read_text())
                state['contentVersion'] = 'unused legacy value'
                session.write_text(json.dumps(state))
                resolve.return_value = ('2' * 40, 'main')
                self.assertEqual(atlas.Atlas(args).ref, '1' * 40)
                resolve.assert_called_once()
                args.command = 'refresh'
                self.assertEqual(atlas.Atlas(args).ref, '2' * 40)
                self.assertNotIn('contentVersion', json.loads(session.read_text()))
                resolve.side_effect = atlas.AtlasError('Cannot resolve latest commit')
                with self.assertRaisesRegex(atlas.AtlasError, 'Cannot resolve'):
                    atlas.Atlas(args)
                self.assertEqual(json.loads(session.read_text())['ref'], '2' * 40)

    def test_case_retrieval_ignores_unrelated_directories_and_legacy_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'agent').mkdir()
            (root / 'agent/catalog.json').write_text(json.dumps({
                'schemaVersion': 1, 'contentVersion': 'unused',
                'entries': [{'id': 'sample', 'paths': {'bundle': 'agent/sample.json'}, 'bundleSha256': 'unused'}],
                'patterns': {'path': 'agent/missing-patterns.json'},
                'materials': {'path': 'agent/missing-materials.json'},
            }))
            (root / 'agent/sample.json').write_text(json.dumps({
                'id': 'sample', 'documents': [{'content': 'context', 'sha256': 'unused'}],
                'files': [{'path': 'demo.html', 'role': 'source', 'sha256': 'unused', 'bytes': 0}],
            }))
            (root / 'demo.html').write_text('<h1>Sample</h1>')
            active = atlas.Atlas(SimpleNamespace(ref=None, local_root=root, session=None, command='show'))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                atlas.show(active, SimpleNamespace(case_id='sample', source=True))
            self.assertEqual(json.loads(output.getvalue())['source'][0]['content'], '<h1>Sample</h1>')
            self.assertIsNone(active.patterns)
            self.assertIsNone(active.materials)

    def test_export_preserves_existing_files_and_removes_its_failed_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / 'export'
            bundle = {'files': [{'path': 'demo.html', 'role': 'source'}, {'path': 'image.png', 'role': 'asset'}]}
            active = SimpleNamespace(entries={'sample': {'paths': {'demo': 'demo.html'}}}, local=root)
            active.bundle = lambda case_id: bundle
            active.provenance = lambda: {'localRoot': str(root)}
            active.read = lambda path: b'<h1>Sample</h1>'
            args = SimpleNamespace(case_id='sample', out=out, code_only=True)
            with contextlib.redirect_stdout(io.StringIO()):
                atlas.export(active, args)
            self.assertEqual((out / 'demo.html').read_text(), '<h1>Sample</h1>')
            self.assertFalse((out / 'image.png').exists())
            with self.assertRaisesRegex(atlas.AtlasError, 'already exists'):
                atlas.export(active, args)
            self.assertTrue((out / 'demo.html').exists())
            args.out = root / 'failed-export'
            args.code_only = False
            with patch.object(active, 'read', side_effect=[b'<h1>Sample</h1>', OSError('download failed')]):
                with self.assertRaisesRegex(OSError, 'download failed'):
                    atlas.export(active, args)
            self.assertFalse(args.out.exists())
            bundle['files'] = [{'path': '../existing.html', 'role': 'source'}]
            with self.assertRaisesRegex(atlas.AtlasError, 'Unsafe repository path'):
                atlas.export(active, args)
            self.assertFalse((root / 'existing.html').exists())


if __name__ == '__main__':
    unittest.main()
