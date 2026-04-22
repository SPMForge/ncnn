from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from scripts.spm import release_state


REPO_ROOT = Path(__file__).resolve().parents[3]
RELEASE_STATE_SCRIPT = REPO_ROOT / "scripts" / "spm" / "release_state.py"


class ReleaseStateTests(unittest.TestCase):
    def test_required_release_asset_names_cover_all_variants(self) -> None:
        self.assertEqual(
            release_state.required_release_asset_names("20260113"),
            (
                "ncnn-20260113-apple.xcframework.zip",
                "ncnn-20260113-apple-vulkan.xcframework.zip",
            ),
        )

    def test_complete_alpha_release_skips(self) -> None:
        payload = release_state.inspect_release_state(
            package_tag="1.0.20260113-alpha.4",
            upstream_tag="20260113",
            release_channel="sync",
            tag_exists=True,
            release_view={
                "isPrerelease": True,
                "assets": [
                    {"name": "ncnn-20260113-apple.xcframework.zip"},
                    {"name": "ncnn-20260113-apple-vulkan.xcframework.zip"},
                ],
            },
            latest_release_tag=None,
        )

        self.assertEqual(payload["mode"], "skip")
        self.assertFalse(payload["metadata_needs_repair"])
        self.assertEqual(payload["missing_assets"], [])

    def test_alpha_release_repairs_metadata_when_latest_or_not_prerelease(self) -> None:
        payload = release_state.inspect_release_state(
            package_tag="1.0.20260113-alpha.4",
            upstream_tag="20260113",
            release_channel="alpha",
            tag_exists=True,
            release_view={
                "isPrerelease": False,
                "assets": [
                    {"name": "ncnn-20260113-apple.xcframework.zip"},
                    {"name": "ncnn-20260113-apple-vulkan.xcframework.zip"},
                ],
            },
            latest_release_tag="1.0.20260113-alpha.4",
        )

        self.assertEqual(payload["mode"], "repair")
        self.assertTrue(payload["metadata_needs_repair"])

    def test_existing_tag_without_release_repairs(self) -> None:
        payload = release_state.inspect_release_state(
            package_tag="1.0.20260113",
            upstream_tag="20260113",
            release_channel="stable",
            tag_exists=True,
            release_view=None,
            latest_release_tag=None,
        )

        self.assertEqual(payload["mode"], "repair")
        self.assertFalse(payload["release_exists"])

    def test_missing_tag_creates_release(self) -> None:
        payload = release_state.inspect_release_state(
            package_tag="1.0.20260113-alpha.5",
            upstream_tag="20260113",
            release_channel="alpha",
            tag_exists=False,
            release_view=None,
            latest_release_tag=None,
        )

        self.assertEqual(payload["mode"], "create")

    def test_script_writes_github_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "github-output.txt"
            release_view_path = Path(temporary_directory) / "release-view.json"
            release_view_path.write_text(
                json.dumps(
                    {
                        "isPrerelease": True,
                        "assets": [
                            {"name": "ncnn-20260113-apple.xcframework.zip"},
                        ],
                    }
                )
            )

            process = subprocess.run(
                [
                    sys.executable,
                    str(RELEASE_STATE_SCRIPT),
                    "inspect-release",
                    "--package-tag",
                    "1.0.20260113-alpha.4",
                    "--upstream-tag",
                    "20260113",
                    "--release-channel",
                    "sync",
                    "--tag-exists",
                    "--release-view-json",
                    str(release_view_path),
                    "--github-output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertIn('"mode": "repair"', process.stdout)
            output_body = output_path.read_text()
            self.assertIn("mode=repair", output_body)
            self.assertIn("missing_assets=ncnn-20260113-apple-vulkan.xcframework.zip", output_body)


if __name__ == "__main__":
    unittest.main()
