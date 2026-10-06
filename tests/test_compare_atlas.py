import importlib.util
from pathlib import Path
import tempfile
import unittest
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/desktop-pet-workflow/scripts/compare_atlas.py'
spec = importlib.util.spec_from_file_location('compare_atlas', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AtlasPreservation(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.before = Path(self.directory.name) / 'before.png'
        self.after = Path(self.directory.name) / 'after.png'
        self.image = Image.new('RGBA', (16, 12), (40, 70, 90, 255))
        self.image.save(self.before, compress_level=0)

    def result(self, allowed):
        return module.compare(self.before, self.after, 4, 3, allowed)

    def test_reencoding_preserves_decoded_pixels(self):
        self.image.save(self.after, compress_level=9)
        result = self.result(set())
        self.assertNotEqual(result['before_sha256'], result['after_sha256'])
        self.assertTrue(result['passed'])

    def test_allowed_change_does_not_hide_unauthorized_change(self):
        self.image.putpixel((4, 5), (0, 0, 0, 255))
        self.image.save(self.after)
        self.assertTrue(self.result({2})['passed'])
        self.image.putpixel((4, 9), (1, 2, 3, 255))
        self.image.save(self.after)
        self.assertEqual(self.result({2})['unexpected_rows'], [3])

    def test_alpha_only_change_is_detected(self):
        self.image.putpixel((0, 0), (40, 70, 90, 0))
        self.image.save(self.after)
        self.assertEqual(self.result(set())['unexpected_rows'], [1])

    def test_dimensions_and_invalid_grid_fail(self):
        Image.new('RGBA', (12, 12)).save(self.after)
        with self.assertRaises(ValueError):
            self.result(set())
        self.image.save(self.after)
        with self.assertRaises(ValueError):
            module.compare(self.before, self.after, 5, 3, set())
        with self.assertRaises(ValueError):
            self.result({0})


if __name__ == '__main__':
    unittest.main()
