import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts.spm import packaging
from scripts.spm import build_apple_xcframework
from scripts.spm import render_package


REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_SWIFT_PATH = REPO_ROOT / "Package.swift"
CURRENT_RELEASE_METADATA_PATH = REPO_ROOT / "scripts" / "spm" / "current_release.json"
PLATFORM_METADATA_PATH = REPO_ROOT / "scripts" / "spm" / "platforms.json"
SMOKE_TEST_PATH = REPO_ROOT / "scripts" / "spm" / "smoke_test_package.py"


class PackageVersionTests(unittest.TestCase):
    def test_maps_upstream_tag_to_alpha_package_tag(self) -> None:
        self.assertEqual(packaging.package_tag_for_upstream_tag("20260113"), "1.0.20260113-alpha.1")

    def test_maps_upstream_tag_to_stable_package_tag(self) -> None:
        self.assertEqual(packaging.stable_package_tag_for_upstream_tag("20260113"), "1.0.20260113")

    def test_maps_upstream_tag_to_package_version(self) -> None:
        self.assertEqual(packaging.package_version_for_upstream_tag("20260113"), "1.0.20260113")

    def test_rejects_invalid_upstream_tag(self) -> None:
        with self.assertRaises(ValueError):
            packaging.package_tag_for_upstream_tag("v20260113")

    def test_finds_next_alpha_number_for_existing_package_refs(self) -> None:
        self.assertEqual(
            packaging.next_alpha_number_for_upstream_tag(
                "20260113",
                [
                    "refs/tags/1.0.20260113-alpha.1",
                    "refs/tags/1.0.20260113-alpha.2",
                    "refs/tags/1.0.20250503-alpha.4",
                ],
            ),
            3,
        )

    def test_ignores_non_matching_refs_when_finding_next_alpha_number(self) -> None:
        self.assertEqual(
            packaging.next_alpha_number_for_upstream_tag(
                "20260113",
                [
                    "refs/tags/1.0.20260113",
                    "refs/tags/1.0.20260113-beta.1",
                    "refs/heads/main",
                ],
            ),
            1,
        )


class AssetNamingTests(unittest.TestCase):
    def test_cpu_asset_name(self) -> None:
        self.assertEqual(
            packaging.asset_name_for_variant(packaging.CPU_VARIANT, "20260113"),
            "ncnn-20260113-apple.xcframework.zip",
        )

    def test_vulkan_asset_name(self) -> None:
        self.assertEqual(
            packaging.asset_name_for_variant(packaging.VULKAN_VARIANT, "20260113"),
            "ncnn-20260113-apple-vulkan.xcframework.zip",
        )


class PlatformMatrixTests(unittest.TestCase):
    def test_cpu_variant_covers_all_expected_apple_slices(self) -> None:
        self.assertEqual(
            [platform.swiftpm_platform for platform in packaging.CPU_VARIANT.platforms],
            [
                "ios",
                "ios-simulator",
                "macos",
                "ios-maccatalyst",
                "tvos",
                "tvos-simulator",
                "watchos",
                "watchos-simulator",
                "xros",
                "xros-simulator",
            ],
        )

    def test_vulkan_variant_excludes_watchos(self) -> None:
        self.assertEqual(
            [platform.swiftpm_platform for platform in packaging.VULKAN_VARIANT.platforms],
            [
                "ios",
                "ios-simulator",
                "macos",
                "ios-maccatalyst",
                "tvos",
                "tvos-simulator",
                "xros",
                "xros-simulator",
            ],
        )


class PackageRenderingTests(unittest.TestCase):
    def test_renders_binary_targets_for_cpu_and_vulkan_products(self) -> None:
        package_contents = packaging.render_package_swift(
            package_name="ncnn",
            owner="SPMForge",
            repo="ncnn",
            releases=[
                packaging.ReleaseAsset(
                    variant=packaging.CPU_VARIANT,
                    upstream_tag="20260113",
                    package_tag="1.0.20260113-alpha.1",
                    checksum="cpu-checksum",
                ),
                packaging.ReleaseAsset(
                    variant=packaging.VULKAN_VARIANT,
                    upstream_tag="20260113",
                    package_tag="1.0.20260113-alpha.1",
                    checksum="vulkan-checksum",
                ),
            ],
        )

        self.assertIn('library(name: "NCNN", targets: ["ncnn"])', package_contents)
        self.assertIn('library(name: "NCNNVulkan", targets: ["ncnn_vulkan"])', package_contents)
        self.assertIn(
            '.binaryTarget(name: "ncnn", url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.1/ncnn-20260113-apple.xcframework.zip", checksum: "cpu-checksum")',
            package_contents,
        )
        self.assertIn(
            '.binaryTarget(name: "ncnn_vulkan", url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.1/ncnn-20260113-apple-vulkan.xcframework.zip", checksum: "vulkan-checksum")',
            package_contents,
        )

    def test_combined_metadata_preserves_requested_package_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "current_release.json"
            render_package._write_combined_metadata(
                output_path=output_path,
                package_name="custom-ncnn",
                owner="SPMForge",
                repo="ncnn",
                releases=[
                    packaging.ReleaseAsset(
                        variant=packaging.CPU_VARIANT,
                        upstream_tag="20260113",
                        package_tag="1.0.20260113-alpha.1",
                        checksum="cpu-checksum",
                    )
                ],
            )

            payload = json.loads(output_path.read_text())
            self.assertEqual(payload["package_name"], "custom-ncnn")


class RootManifestTests(unittest.TestCase):
    def _write_manifest_fixture(
        self,
        package_root: Path,
        current_release_payload: str | None = None,
    ) -> None:
        (package_root / "scripts" / "spm").mkdir(parents=True)
        shutil.copy2(PACKAGE_SWIFT_PATH, package_root / "Package.swift")
        if PLATFORM_METADATA_PATH.exists():
            shutil.copy2(PLATFORM_METADATA_PATH, package_root / "scripts" / "spm" / "platforms.json")
        if current_release_payload is None:
            shutil.copy2(CURRENT_RELEASE_METADATA_PATH, package_root / "scripts" / "spm" / "current_release.json")
        else:
            (package_root / "scripts" / "spm" / "current_release.json").write_text(current_release_payload)

    def _dump_package(self, package_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["swift", "package", "dump-package"],
            cwd=package_root,
            capture_output=True,
            text=True,
        )

    def test_root_manifest_uses_expected_package_platform_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = Path(temporary_directory)
            self._write_manifest_fixture(package_root)

            process = self._dump_package(package_root)

            self.assertEqual(process.returncode, 0, msg=process.stderr)
            payload = json.loads(process.stdout)
            platforms = {item["platformName"]: item["version"] for item in payload["platforms"]}
            self.assertEqual(
                platforms,
                {
                    "ios": "13.0",
                    "macos": "11.0",
                    "maccatalyst": "13.1",
                    "tvos": "11.0",
                    "watchos": "6.0",
                    "visionos": "1.0",
                },
            )

    def test_root_manifest_fails_when_release_metadata_is_malformed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = Path(temporary_directory)
            self._write_manifest_fixture(package_root, current_release_payload="{}\n")

            process = self._dump_package(package_root)

            self.assertNotEqual(process.returncode, 0)
            self.assertIn("current_release.json", process.stderr)


class SmokeTestScriptTests(unittest.TestCase):
    def test_release_validation_uses_merged_binary_type_automatic(self) -> None:
        script = SMOKE_TEST_PATH.read_text()

        self.assertIn("MERGED_BINARY_TYPE=automatic", script)
        self.assertIn("xcodebuild", script)
        self.assertIn("NCNNSmoke", script)

    def test_smoke_test_stages_xcframework_under_package_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            package_root = temporary_root / "consumer"
            xcframework_path = temporary_root / "fixtures" / "ncnn.xcframework"
            xcframework_path.mkdir(parents=True)
            (xcframework_path / "Info.plist").write_text("fixture")

            from scripts.spm import smoke_test_package

            smoke_test_package._write_consumer_package(
                package_root,
                packaging.CPU_VARIANT,
                xcframework_path,
            )

            manifest = (package_root / "Package.swift").read_text()
            self.assertIn('.binaryTarget(name: "ncnn", path: "Artifacts/ncnn.xcframework")', manifest)
            self.assertNotIn(str(xcframework_path), manifest)
            self.assertTrue((package_root / "Artifacts" / "ncnn.xcframework" / "Info.plist").exists())


class BuildCommandTests(unittest.TestCase):
    def test_watchos_arm64_32_slice_skips_install_name_rewrite(self) -> None:
        self.assertFalse(
            build_apple_xcframework._should_rewrite_install_name(
                packaging.CPU_VARIANT.platforms[6]
            )
        )

    def test_non_watchos_slice_rewrites_install_name(self) -> None:
        self.assertTrue(
            build_apple_xcframework._should_rewrite_install_name(
                packaging.CPU_VARIANT.platforms[0]
            )
        )

    def test_cmake_configure_disables_code_signing_for_generated_xcode_project(self) -> None:
        with mock.patch.object(build_apple_xcframework, "_compiler_launcher_flags", return_value=[]):
            command = build_apple_xcframework._cmake_configure_command(
                packaging.CPU_VARIANT,
                packaging.CPU_VARIANT.platforms[0],
                source_root=Path("/tmp/source"),
                build_dir=Path("/tmp/build"),
                install_dir=Path("/tmp/install"),
            )

        self.assertIn("-DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED=NO", command)
        self.assertIn("-DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_REQUIRED=NO", command)
        self.assertIn("-DCMAKE_XCODE_ATTRIBUTE_CODE_SIGN_STYLE=Manual", command)

    def test_cmake_configure_uses_ccache_launcher_when_available(self) -> None:
        with mock.patch.object(
            build_apple_xcframework,
            "_compiler_launcher_flags",
            return_value=["-DCMAKE_C_COMPILER_LAUNCHER=/opt/homebrew/bin/ccache", "-DCMAKE_CXX_COMPILER_LAUNCHER=/opt/homebrew/bin/ccache"],
        ):
            command = build_apple_xcframework._cmake_configure_command(
                packaging.CPU_VARIANT,
                packaging.CPU_VARIANT.platforms[0],
                source_root=Path("/tmp/source"),
                build_dir=Path("/tmp/build"),
                install_dir=Path("/tmp/install"),
            )

        self.assertIn("-DCMAKE_C_COMPILER_LAUNCHER=/opt/homebrew/bin/ccache", command)
        self.assertIn("-DCMAKE_CXX_COMPILER_LAUNCHER=/opt/homebrew/bin/ccache", command)

    def test_cmake_build_install_disables_code_signing(self) -> None:
        command = build_apple_xcframework._build_command(Path("/tmp/build"))

        self.assertEqual(command[:6], ["cmake", "--build", "/tmp/build", "--config", "Release", "--target"])
        self.assertIn("CODE_SIGNING_ALLOWED=NO", command)
        self.assertIn("CODE_SIGNING_REQUIRED=NO", command)
        self.assertIn("CODE_SIGN_STYLE=Manual", command)


if __name__ == "__main__":
    unittest.main()
