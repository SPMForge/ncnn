from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from scripts.spm import archive_builder
from scripts.spm import packaging
from scripts.spm import tag_selection


REPO_ROOT = Path(__file__).resolve().parents[3]
SELECT_UPSTREAM_TAG_SCRIPT = REPO_ROOT / "scripts" / "spm" / "select_upstream_tag.py"


class LatestStableTagTests(unittest.TestCase):
    def test_selects_latest_numeric_date_tag(self) -> None:
        self.assertEqual(
            tag_selection.select_latest_stable_tag(
                [
                    "refs/tags/v1.2.3",
                    "refs/tags/20240410",
                    "refs/tags/20260113",
                    "refs/tags/20250503",
                ]
            ),
            "20260113",
        )

    def test_accepts_upstream_tag_ref_namespace(self) -> None:
        self.assertEqual(
            tag_selection.select_latest_stable_tag(
                [
                    "refs/upstream-tags/20240410",
                    "refs/upstream-tags/20260113",
                    "refs/upstream-tags/20250503",
                ]
            ),
            "20260113",
        )

    def test_rejects_when_no_stable_tag_is_available(self) -> None:
        with self.assertRaises(ValueError):
            tag_selection.select_latest_stable_tag(["refs/tags/v1.2.3", "refs/tags/latest"])


class ArchiveDiscoveryTests(unittest.TestCase):
    def test_prefers_xcarchive_product_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_root = Path(temporary_directory) / "ncnn.xcarchive"
            archive_binary = archive_root / "Products" / "usr" / "local" / "lib" / "libncnn.1.dylib"
            archive_binary.parent.mkdir(parents=True)
            archive_binary.write_bytes(b"archive-product")

            fallback_binary = (
                Path(temporary_directory)
                / "DerivedData"
                / "ArchiveIntermediates"
                / "ncnn"
                / "IntermediateBuildFilesPath"
                / "UninstalledProducts"
                / "macosx"
                / "libncnn.1.dylib"
            )
            fallback_binary.parent.mkdir(parents=True)
            fallback_binary.write_bytes(b"fallback-product")

            self.assertEqual(
                archive_builder.find_dynamic_library(
                    archive_root=archive_root,
                    derived_data_root=Path(temporary_directory) / "DerivedData",
                    library_basename="ncnn",
                ),
                archive_binary,
            )

    def test_falls_back_to_uninstalled_products(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_root = Path(temporary_directory) / "ncnn.xcarchive"
            archive_root.mkdir(parents=True)

            fallback_binary = (
                Path(temporary_directory)
                / "DerivedData"
                / "ArchiveIntermediates"
                / "ncnn"
                / "IntermediateBuildFilesPath"
                / "UninstalledProducts"
                / "ios"
                / "libncnn.1.0.26.04.18.dylib"
            )
            fallback_binary.parent.mkdir(parents=True)
            fallback_binary.write_bytes(b"fallback-product")

            self.assertEqual(
                archive_builder.find_dynamic_library(
                    archive_root=archive_root,
                    derived_data_root=Path(temporary_directory) / "DerivedData",
                    library_basename="ncnn",
                ),
                fallback_binary,
            )

    def test_errors_when_no_dynamic_library_is_found(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_root = Path(temporary_directory) / "ncnn.xcarchive"
            archive_root.mkdir(parents=True)

            with self.assertRaises(FileNotFoundError):
                archive_builder.find_dynamic_library(
                    archive_root=archive_root,
                    derived_data_root=Path(temporary_directory) / "DerivedData",
                    library_basename="ncnn",
                )


class SelectUpstreamTagScriptTests(unittest.TestCase):
    def _init_git_repo(self, repo_root: Path) -> None:
        subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo_root, check=True, capture_output=True, text=True)

    def _run_script(self, repo_root: Path, *args: str) -> dict[str, str]:
        process = subprocess.run(
            [sys.executable, str(SELECT_UPSTREAM_TAG_SCRIPT), "--repo-root", str(repo_root), *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 0, msg=process.stderr)
        return json.loads(process.stdout)

    def _commit_file(self, repo_root: Path, relative_path: str, contents: str, message: str) -> None:
        file_path = repo_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(contents)
        subprocess.run(["git", "add", relative_path], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True, capture_output=True, text=True)

    def test_sync_mode_uses_alpha_1_package_tag_when_no_alpha_release_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._init_git_repo(repo_root)

            payload = self._run_script(repo_root, "--explicit-tag", "20260113")

            self.assertEqual(
                payload,
                {
                    "upstream_tag": "20260113",
                    "build_tag": packaging.package_tag_for_upstream_tag("20260113"),
                    "package_tag": packaging.package_tag_for_upstream_tag("20260113"),
                    "latest_package_tag": "",
                    "next_package_tag": packaging.package_tag_for_upstream_tag("20260113"),
                    "remote_tag_exists": False,
                    "remote_tag_commit": "",
                },
            )

    def test_sync_mode_reuses_latest_alpha_tag_when_head_already_matches_latest_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._init_git_repo(repo_root)
            subprocess.run(["git", "tag", "1.0.20260113-alpha.1"], cwd=repo_root, check=True, capture_output=True, text=True)

            payload = self._run_script(repo_root, "--explicit-tag", "20260113")

            self.assertEqual(
                payload,
                {
                    "upstream_tag": "20260113",
                    "build_tag": "1.0.20260113-alpha.1",
                    "package_tag": "1.0.20260113-alpha.1",
                    "latest_package_tag": "1.0.20260113-alpha.1",
                    "next_package_tag": "1.0.20260113-alpha.2",
                    "remote_tag_exists": True,
                    "remote_tag_commit": subprocess.run(
                        ["git", "rev-parse", "refs/tags/1.0.20260113-alpha.1^{commit}"],
                        cwd=repo_root,
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout.strip(),
                },
            )

    def test_sync_mode_keeps_latest_alpha_as_build_tag_when_head_has_advanced_since_latest_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._init_git_repo(repo_root)
            subprocess.run(["git", "tag", "1.0.20260113-alpha.1"], cwd=repo_root, check=True, capture_output=True, text=True)
            self._commit_file(repo_root, "packaging.txt", "updated packaging logic\n", "packaging update")

            payload = self._run_script(repo_root, "--explicit-tag", "20260113")

            self.assertEqual(
                payload,
                {
                    "upstream_tag": "20260113",
                    "build_tag": "1.0.20260113-alpha.1",
                    "package_tag": "1.0.20260113-alpha.1",
                    "latest_package_tag": "1.0.20260113-alpha.1",
                    "next_package_tag": "1.0.20260113-alpha.2",
                    "remote_tag_exists": True,
                    "remote_tag_commit": subprocess.run(
                        ["git", "rev-parse", "refs/tags/1.0.20260113-alpha.1^{commit}"],
                        cwd=repo_root,
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout.strip(),
                },
            )

    def test_backfill_mode_bumps_alpha_number_when_package_tag_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._init_git_repo(repo_root)
            subprocess.run(["git", "tag", "1.0.20260113-alpha.1"], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "tag", "1.0.20260113-alpha.2"], cwd=repo_root, check=True, capture_output=True, text=True)

            payload = self._run_script(repo_root, "--explicit-tag", "20260113", "--release-channel", "backfill")

            self.assertEqual(
                payload,
                {
                    "upstream_tag": "20260113",
                    "build_tag": "1.0.20260113-alpha.3",
                    "package_tag": "1.0.20260113-alpha.3",
                    "latest_package_tag": "1.0.20260113-alpha.2",
                    "next_package_tag": "1.0.20260113-alpha.3",
                    "remote_tag_exists": False,
                    "remote_tag_commit": "",
                },
            )

    def test_stable_mode_uses_stable_package_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._init_git_repo(repo_root)
            subprocess.run(["git", "tag", "1.0.20260113-alpha.1"], cwd=repo_root, check=True, capture_output=True, text=True)

            payload = self._run_script(repo_root, "--explicit-tag", "20260113", "--release-channel", "stable")

            self.assertEqual(
                payload,
                {
                    "upstream_tag": "20260113",
                    "build_tag": "1.0.20260113",
                    "package_tag": "1.0.20260113",
                    "latest_package_tag": "",
                    "next_package_tag": "",
                    "remote_tag_exists": False,
                    "remote_tag_commit": "",
                },
            )

    def test_writes_remote_tag_outputs_for_existing_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._init_git_repo(repo_root)
            subprocess.run(["git", "tag", "1.0.20260113-alpha.1"], cwd=repo_root, check=True, capture_output=True, text=True)
            output_path = repo_root / "github-output.txt"

            process = subprocess.run(
                [
                    sys.executable,
                    str(SELECT_UPSTREAM_TAG_SCRIPT),
                    "--repo-root",
                    str(repo_root),
                    "--explicit-tag",
                    "20260113",
                    "--github-output",
                    str(output_path),
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            payload = json.loads(process.stdout)
            output_body = output_path.read_text()
            self.assertTrue(payload["remote_tag_exists"])
            self.assertIn("build_tag=1.0.20260113-alpha.1", output_body)
            self.assertIn("latest_package_tag=1.0.20260113-alpha.1", output_body)
            self.assertIn("next_package_tag=1.0.20260113-alpha.2", output_body)
            self.assertIn("remote_tag_exists=true", output_body)
            self.assertIn(f"remote_tag_commit={payload['remote_tag_commit']}", output_body)


if __name__ == "__main__":
    unittest.main()
