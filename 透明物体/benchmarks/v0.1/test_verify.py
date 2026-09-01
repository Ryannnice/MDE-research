import json
import tempfile
import unittest
from pathlib import Path

from verify import DEFAULT_MANIFEST, DEFAULT_ROOT, verify_manifest


class BenchmarkManifestTest(unittest.TestCase):
    def test_repository_manifest_passes(self):
        self.assertEqual(verify_manifest(DEFAULT_MANIFEST, DEFAULT_ROOT), [])

    def test_changed_denominator_is_rejected(self):
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        manifest["frozen_result_invariants"][0]["value"] = 999
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = verify_manifest(path, DEFAULT_ROOT)
        self.assertTrue(any("p0.booster.samples" in error for error in errors))

    def test_training_leakage_flag_is_rejected(self):
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        manifest["evaluation_splits"]["layereddepth_real_validation"]["allow_training"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = verify_manifest(path, DEFAULT_ROOT)
        self.assertTrue(any("layereddepth_real_validation" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
