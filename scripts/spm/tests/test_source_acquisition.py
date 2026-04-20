from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ACQUISITION_SCRIPT = REPO_ROOT / "scripts" / "spm" / "source_acquisition.py"
SOURCE_ACQUISITION_CONTRACT = REPO_ROOT / "scripts" / "spm" / "source_acquisition.json"


class SourceAcquisitionContractTests(unittest.TestCase):
    def test_contract_file_exists(self) -> None:
        self.assertTrue(SOURCE_ACQUISITION_CONTRACT.exists())

    def test_fetch_tags_requires_explicit_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            process = subprocess.run(
                [
                    sys.executable,
                    str(SOURCE_ACQUISITION_SCRIPT),
                    "fetch-tags",
                    "--repo-root",
                    str(repo_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("source acquisition contract", process.stderr)

    def test_help_mentions_export_source_command(self) -> None:
        process = subprocess.run(
            [sys.executable, str(SOURCE_ACQUISITION_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, msg=process.stderr)
        self.assertIn("export-source", process.stdout)


if __name__ == "__main__":
    unittest.main()
