import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts.spm import packaging
from scripts.spm import build_apple_xcframework
from scripts.spm import preflight_apple_platforms
from scripts.spm import render_package
from scripts.spm import validate_package_contract


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


class ValidationWorkflowHelperTests(unittest.TestCase):
    def test_validate_package_contract_accepts_fresh_release_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            repo_root = temporary_root / "repo"
            (repo_root / "scripts" / "spm").mkdir(parents=True)
            shutil.copy2(PACKAGE_SWIFT_PATH, repo_root / "Package.swift")
            shutil.copy2(PLATFORM_METADATA_PATH, repo_root / "scripts" / "spm" / "platforms.json")

            cpu_metadata_path = temporary_root / "ncnn.release.json"
            cpu_metadata_path.write_text(
                json.dumps(
                    {
                        "target_name": "ncnn",
                        "upstream_tag": "20260113",
                        "package_tag": "1.0.20260113-alpha.1",
                        "checksum": "cpu-checksum",
                    }
                )
            )
            vulkan_metadata_path = temporary_root / "ncnn_vulkan.release.json"
            vulkan_metadata_path.write_text(
                json.dumps(
                    {
                        "target_name": "ncnn_vulkan",
                        "upstream_tag": "20260113",
                        "package_tag": "1.0.20260113-alpha.1",
                        "checksum": "vulkan-checksum",
                    }
                )
            )

            process = subprocess.run(
                [
                    "python3",
                    str(REPO_ROOT / "scripts" / "spm" / "validate_package_contract.py"),
                    "--repo-root",
                    str(repo_root),
                    "--release-metadata",
                    str(cpu_metadata_path),
                    "--release-metadata",
                    str(vulkan_metadata_path),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(process.returncode, 0, msg=process.stderr)
            payload = json.loads(process.stdout)
            self.assertEqual(payload["release_count"], 2)
            self.assertIn("package_root", payload)

    def test_preflight_rejects_required_platform_drift_from_variant_contract(self) -> None:
        with self.assertRaises(ValueError):
            preflight_apple_platforms._validate_required_platforms(
                packaging.CPU_VARIANT,
                ["ios", "macos"],
            )

    def test_preflight_checks_sdk_access_for_each_required_platform(self) -> None:
        with mock.patch.object(
            preflight_apple_platforms,
            "_capture_output",
            side_effect=[
                "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS.sdk",
                "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator.sdk",
            ],
        ):
            payload = preflight_apple_platforms._preflight_sdk_support(["ios", "ios-simulator"])

        self.assertEqual(
            payload,
            [
                {
                    "platform": "ios",
                    "sdk": "iphoneos",
                    "sdk_path": "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS.sdk",
                },
                {
                    "platform": "ios-simulator",
                    "sdk": "iphonesimulator",
                    "sdk_path": "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator.sdk",
                },
            ],
        )

    def test_preflight_reports_install_hint_when_sdk_support_is_missing(self) -> None:
        with mock.patch.object(
            preflight_apple_platforms,
            "_capture_output",
            side_effect=RuntimeError("xcrun: error: SDK \"xros\" cannot be located"),
        ):
            with self.assertRaisesRegex(RuntimeError, "xcodebuild -downloadPlatform visionOS"):
                preflight_apple_platforms._preflight_sdk_support(["xros"])


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

    def test_cmake_configure_does_not_use_compiler_launcher_flags(self) -> None:
        command = build_apple_xcframework._cmake_configure_command(
            packaging.CPU_VARIANT,
            packaging.CPU_VARIANT.platforms[0],
            source_root=Path("/tmp/source"),
            build_dir=Path("/tmp/build"),
            install_dir=Path("/tmp/install"),
        )

        self.assertNotIn("-DCMAKE_C_COMPILER_LAUNCHER=ccache", command)
        self.assertNotIn("-DCMAKE_CXX_COMPILER_LAUNCHER=ccache", command)

    def test_compiler_cache_environment_uses_wrapper_binaries_when_ccache_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            wrapper_root = Path(temporary_directory)
            environment = {
                "CCACHE_DIR": str(wrapper_root / ".ccache"),
                "PATH": "/usr/bin:/bin",
            }

            with (
                mock.patch("scripts.spm.build_apple_xcframework.shutil.which", return_value="/opt/homebrew/bin/ccache"),
                mock.patch.object(
                    build_apple_xcframework,
                    "_capture_output",
                    side_effect=["/usr/bin/clang", "/usr/bin/clang++"],
                ),
            ):
                cached_environment = build_apple_xcframework._compiler_cache_environment(environment, wrapper_root)

            self.assertEqual(cached_environment["CC"], str(wrapper_root / ".compiler-wrappers" / "clang"))
            self.assertEqual(cached_environment["CXX"], str(wrapper_root / ".compiler-wrappers" / "clang++"))
            self.assertEqual(cached_environment["OBJC"], str(wrapper_root / ".compiler-wrappers" / "clang"))
            self.assertEqual(cached_environment["OBJCXX"], str(wrapper_root / ".compiler-wrappers" / "clang++"))
            self.assertEqual(cached_environment["LDPLUSPLUS"], str(wrapper_root / ".compiler-wrappers" / "clang++"))
            self.assertTrue((wrapper_root / ".ccache").exists())
            self.assertTrue((wrapper_root / ".compiler-wrappers" / "clang").exists())
            self.assertIn('exec "/opt/homebrew/bin/ccache" "/usr/bin/clang" "$@"', (wrapper_root / ".compiler-wrappers" / "clang").read_text())

    def test_cmake_build_install_disables_code_signing(self) -> None:
        command = build_apple_xcframework._build_command(Path("/tmp/build"))

        self.assertEqual(command[:6], ["cmake", "--build", "/tmp/build", "--config", "Release", "--target"])
        self.assertIn("CODE_SIGNING_ALLOWED=NO", command)
        self.assertIn("CODE_SIGNING_REQUIRED=NO", command)
        self.assertIn("CODE_SIGN_STYLE=Manual", command)

    def test_stage_framework_bundle_creates_versioned_macos_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            headers_source = temporary_root / "Headers"
            headers_source.mkdir()
            (headers_source / "net.h").write_text("// header")
            (headers_source / "module.modulemap").write_text("module ncnn { export * }")
            source_binary = temporary_root / "libncnn.1.dylib"
            source_binary.write_bytes(b"binary")

            with mock.patch.object(build_apple_xcframework, "_run") as run_mock:
                framework_path = build_apple_xcframework._stage_framework_bundle(
                    source_binary=source_binary,
                    headers_source=headers_source,
                    output_dir=temporary_root / "staging",
                    bundle_name="ncnn",
                    module_name="ncnn",
                    platform=packaging.CPU_VARIANT.platforms[2],
                    environment={"PATH": "/usr/bin:/bin"},
                )

            self.assertEqual(framework_path, temporary_root / "staging" / "ncnn.framework")
            self.assertTrue((framework_path / "Versions" / "A" / "ncnn").exists())
            self.assertTrue((framework_path / "Versions" / "Current").is_symlink())
            self.assertEqual((framework_path / "Versions" / "Current").readlink(), Path("A"))
            self.assertTrue((framework_path / "ncnn").is_symlink())
            self.assertEqual((framework_path / "ncnn").readlink(), Path("Versions") / "Current" / "ncnn")
            self.assertTrue((framework_path / "Headers").is_symlink())
            self.assertTrue((framework_path / "Modules").is_symlink())
            self.assertTrue((framework_path / "Resources").is_symlink())
            self.assertTrue((framework_path / "Versions" / "A" / "Resources" / "Info.plist").exists())
            self.assertTrue((framework_path / "Versions" / "A" / "Modules" / "module.modulemap").exists())
            self.assertFalse((framework_path / "Versions" / "A" / "Headers" / "module.modulemap").exists())
            run_mock.assert_called_once_with(
                [
                    "install_name_tool",
                    "-id",
                    "@rpath/ncnn.framework/Versions/A/ncnn",
                    str(framework_path / "Versions" / "A" / "ncnn"),
                ],
                env={"PATH": "/usr/bin:/bin"},
            )

    def test_create_xcframework_accepts_framework_and_library_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            headers_path = temporary_root / "Headers"
            headers_path.mkdir()
            staged_library = temporary_root / "libncnn.dylib"
            staged_library.write_bytes(b"binary")
            staged_framework = temporary_root / "ncnn.framework"
            staged_framework.mkdir()

            with mock.patch.object(build_apple_xcframework, "_run") as run_mock:
                output_path = build_apple_xcframework._create_xcframework(
                    variant=packaging.CPU_VARIANT,
                    headers_path=headers_path,
                    staged_libraries=[staged_library],
                    staged_frameworks=[staged_framework],
                    output_dir=temporary_root,
                    environment={"PATH": "/usr/bin:/bin"},
                )

            self.assertEqual(output_path, temporary_root / "ncnn.xcframework")
            run_mock.assert_called_once_with(
                [
                    "xcodebuild",
                    "-create-xcframework",
                    "-library",
                    str(staged_library),
                    "-headers",
                    str(headers_path),
                    "-framework",
                    str(staged_framework),
                    "-output",
                    str(temporary_root / "ncnn.xcframework"),
                ],
                env={"PATH": "/usr/bin:/bin"},
            )


if __name__ == "__main__":
    unittest.main()
