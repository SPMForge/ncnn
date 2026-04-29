import argparse
import hashlib
import io
import json
import plistlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

from scripts.spm import packaging
from scripts.spm import build_apple_xcframework
from scripts.spm import preflight_apple_platforms
from scripts.spm import prepare_moltenvk_dependency
from scripts.spm import render_package
from scripts.spm import validate_package_contract
from scripts.spm import verify_sop_conformance


REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_SWIFT_PATH = REPO_ROOT / "Package.swift"
CURRENT_RELEASE_METADATA_PATH = REPO_ROOT / "scripts" / "spm" / "current_release.json"
PLATFORM_METADATA_PATH = REPO_ROOT / "scripts" / "spm" / "platforms.json"
SMOKE_TEST_PATH = REPO_ROOT / "scripts" / "spm" / "smoke_test_package.py"


class PrepareMoltenVKDependencyTests(unittest.TestCase):
    def test_stages_framework_and_provider_headers_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            output_dir = temporary_root / "moltenvk"
            output_dir.mkdir()
            framework_zip = output_dir / f"MoltenVK-{packaging.MOLTENVK_PACKAGE.exact_version}.xcframework.zip"
            headers_zip = output_dir / f"MoltenVKHeaders-{packaging.MOLTENVK_PACKAGE.exact_version}.zip"
            github_output = temporary_root / "github-output"

            with zipfile.ZipFile(framework_zip, "w") as archive:
                archive.writestr("MoltenVK.xcframework/Info.plist", "<plist/>")
            with zipfile.ZipFile(headers_zip, "w") as archive:
                archive.writestr("include/vulkan/vulkan.h", "#include <MoltenVK/vulkan/vk_platform.h>\n")
                archive.writestr("include/MoltenVK/vulkan/vk_platform.h", "// vk_platform\n")

            with (
                mock.patch.object(packaging, "MOLTENVK_ARTIFACT_CHECKSUM", self._sha256(framework_zip)),
                mock.patch.object(packaging, "MOLTENVK_HEADERS_ARTIFACT_CHECKSUM", self._sha256(headers_zip)),
                mock.patch(
                    "sys.argv",
                    [
                        "prepare_moltenvk_dependency.py",
                        "--output-dir",
                        str(output_dir),
                        "--github-output",
                        str(github_output),
                    ],
                ),
                mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
            ):
                self.assertEqual(prepare_moltenvk_dependency.main(), 0)

            payload = json.loads(stdout.getvalue())
            resolved_output_dir = output_dir.resolve()
            headers_include_dir = resolved_output_dir / "headers-extracted" / "include"
            self.assertEqual(payload["xcframework_path"], str(resolved_output_dir / "extracted" / "MoltenVK.xcframework"))
            self.assertEqual(payload["headers_zip_path"], str(resolved_output_dir / headers_zip.name))
            self.assertEqual(payload["headers_include_dir"], str(headers_include_dir))
            self.assertIn(f"headers_include_dir={headers_include_dir}", github_output.read_text())

    def test_stages_explicit_development_version_with_release_asset_digests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            output_dir = temporary_root / "moltenvk"
            output_dir.mkdir()
            version = "1.4.1-alpha.99"
            framework_zip = output_dir / f"MoltenVK-{version}.xcframework.zip"
            headers_zip = output_dir / f"MoltenVKHeaders-{version}.zip"

            with zipfile.ZipFile(framework_zip, "w") as archive:
                archive.writestr("MoltenVK.xcframework/Info.plist", "<plist/>")
            with zipfile.ZipFile(headers_zip, "w") as archive:
                archive.writestr("include/vulkan/vulkan.h", "#include <MoltenVK/vulkan/vk_platform.h>\n")
                archive.writestr("include/MoltenVK/vulkan/vk_platform.h", "// vk_platform\n")

            release_checksums = {
                framework_zip.name: self._sha256(framework_zip),
                headers_zip.name: self._sha256(headers_zip),
            }

            with (
                mock.patch(
                    "sys.argv",
                    [
                        "prepare_moltenvk_dependency.py",
                        "--output-dir",
                        str(output_dir),
                        "--version",
                        version,
                    ],
                ),
                mock.patch.object(
                    prepare_moltenvk_dependency,
                    "_release_asset_checksum",
                    side_effect=lambda requested_version, asset_name: release_checksums[asset_name],
                ) as release_asset_checksum,
                mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
            ):
                self.assertEqual(prepare_moltenvk_dependency.main(), 0)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["version"], version)
            self.assertEqual(payload["headers_zip_path"], str(output_dir.resolve() / headers_zip.name))
            self.assertEqual(payload["xcframework_checksum"], self._sha256(framework_zip))
            self.assertEqual(payload["headers_checksum"], self._sha256(headers_zip))
            self.assertEqual(release_asset_checksum.call_count, 2)

    def test_writes_repo_local_dependency_pin_without_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            output_dir = temporary_root / "moltenvk"
            output_dir.mkdir()
            version = "1.4.1-alpha.99"
            framework_zip = output_dir / f"MoltenVK-{version}.xcframework.zip"
            headers_zip = output_dir / f"MoltenVKHeaders-{version}.zip"
            pin_path = temporary_root / "moltenvk_dependency.json"

            with zipfile.ZipFile(framework_zip, "w") as archive:
                archive.writestr("MoltenVK.xcframework/Info.plist", "<plist/>")
            with zipfile.ZipFile(headers_zip, "w") as archive:
                archive.writestr("include/vulkan/vulkan.h", "#include <MoltenVK/vulkan/vk_platform.h>\n")
                archive.writestr("include/MoltenVK/vulkan/vk_platform.h", "// vk_platform\n")

            with (
                mock.patch(
                    "sys.argv",
                    [
                        "prepare_moltenvk_dependency.py",
                        "--output-dir",
                        str(output_dir),
                        "--version",
                        version,
                        "--xcframework-checksum",
                        self._sha256(framework_zip),
                        "--headers-checksum",
                        self._sha256(headers_zip),
                        "--write-pin",
                        str(pin_path),
                    ],
                ),
                mock.patch("sys.stdout", new_callable=io.StringIO),
            ):
                self.assertEqual(prepare_moltenvk_dependency.main(), 0)

            pin = json.loads(pin_path.read_text())
            self.assertEqual(pin["version"], version)
            self.assertEqual(pin["package_name"], "MoltenVK")
            self.assertEqual(pin["url"], "https://github.com/SPMForge/MoltenVK.git")
            self.assertNotIn("xcframework_checksum", pin)
            self.assertNotIn("headers_checksum", pin)

    def test_latest_writes_default_repo_local_dependency_pin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            output_dir = temporary_root / "moltenvk"
            output_dir.mkdir()
            version = "1.4.1-alpha.100"
            framework_zip = output_dir / f"MoltenVK-{version}.xcframework.zip"
            headers_zip = output_dir / f"MoltenVKHeaders-{version}.zip"
            pin_path = temporary_root / "moltenvk_dependency.json"

            with zipfile.ZipFile(framework_zip, "w") as archive:
                archive.writestr("MoltenVK.xcframework/Info.plist", "<plist/>")
            with zipfile.ZipFile(headers_zip, "w") as archive:
                archive.writestr("include/vulkan/vulkan.h", "#include <MoltenVK/vulkan/vk_platform.h>\n")
                archive.writestr("include/MoltenVK/vulkan/vk_platform.h", "// vk_platform\n")

            releases_payload = [
                {
                    "tag_name": "1.4.1-alpha.99",
                    "assets": [{"name": "MoltenVK-1.4.1-alpha.99.xcframework.zip"}],
                },
                {
                    "tag_name": version,
                    "assets": [
                        {"name": framework_zip.name},
                        {"name": headers_zip.name},
                    ],
                },
            ]

            with (
                mock.patch.object(prepare_moltenvk_dependency, "DEFAULT_OUTPUT_DIR", output_dir),
                mock.patch.object(packaging, "MOLTENVK_DEPENDENCY_CONFIG_PATH", pin_path),
                mock.patch.object(prepare_moltenvk_dependency, "_github_json", return_value=releases_payload),
                mock.patch(
                    "sys.argv",
                    [
                        "prepare_moltenvk_dependency.py",
                        "--latest",
                        "--xcframework-checksum",
                        self._sha256(framework_zip),
                        "--headers-checksum",
                        self._sha256(headers_zip),
                        "--write-pin",
                    ],
                ),
                mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
            ):
                self.assertEqual(prepare_moltenvk_dependency.main(), 0)

            payload = json.loads(stdout.getvalue())
            pin = json.loads(pin_path.read_text())
            self.assertEqual(payload["version"], version)
            self.assertEqual(payload["xcframework_checksum"], self._sha256(framework_zip))
            self.assertEqual(payload["headers_checksum"], self._sha256(headers_zip))
            self.assertEqual(pin["version"], version)
            self.assertNotIn("xcframework_checksum", pin)
            self.assertNotIn("headers_checksum", pin)

    def test_github_json_uses_actions_token_when_available(self) -> None:
        class Response:
            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"ok": true}'

        with (
            mock.patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}),
            mock.patch.object(prepare_moltenvk_dependency.urllib.request, "urlopen", return_value=Response()) as urlopen,
        ):
            self.assertEqual(prepare_moltenvk_dependency._github_json("https://api.github.com/test"), {"ok": True})

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")

    def test_rejects_incomplete_provider_headers_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            include_root = Path(temporary_directory) / "include"
            (include_root / "vulkan").mkdir(parents=True)
            (include_root / "vulkan" / "vulkan.h").write_text("// missing MoltenVK self-include surface\n")

            with self.assertRaisesRegex(ValueError, "expected one MoltenVK headers include directory"):
                prepare_moltenvk_dependency._find_moltenvk_headers_include_dir(Path(temporary_directory))

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as input_file:
            for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


class MoltenVKDependencyConfigTests(unittest.TestCase):
    def test_accepts_dependency_pin_without_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            pin_path = Path(temporary_directory) / "moltenvk_dependency.json"
            pin_path.write_text(
                json.dumps(
                    {
                        "package_name": "MoltenVK",
                        "url": "https://github.com/SPMForge/MoltenVK.git",
                        "version": "1.4.1-alpha.99",
                    }
                )
            )

            with mock.patch.object(packaging, "MOLTENVK_DEPENDENCY_CONFIG_PATH", pin_path):
                config = packaging._load_moltenvk_dependency_config()

            self.assertEqual(config["version"], "1.4.1-alpha.99")
            self.assertEqual(config["xcframework_checksum"], "")
            self.assertEqual(config["headers_checksum"], "")


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

    def test_finds_latest_alpha_package_tag_for_existing_package_refs(self) -> None:
        self.assertEqual(
            packaging.latest_alpha_package_tag_for_upstream_tag(
                "20260113",
                [
                    "refs/tags/1.0.20260113-alpha.1",
                    "refs/tags/1.0.20260113-alpha.3",
                    "refs/tags/1.0.20260113-alpha.2",
                    "refs/tags/1.0.20250503-alpha.4",
                ],
            ),
            "1.0.20260113-alpha.3",
        )

    def test_returns_none_when_no_matching_alpha_package_tag_exists(self) -> None:
        self.assertIsNone(
            packaging.latest_alpha_package_tag_for_upstream_tag(
                "20260113",
                [
                    "refs/tags/1.0.20260113",
                    "refs/tags/1.0.20260113-beta.1",
                    "refs/heads/main",
                ],
            )
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

    def test_vulkan_variant_excludes_unsupported_provider_platforms(self) -> None:
        self.assertEqual(
            [platform.swiftpm_platform for platform in packaging.VULKAN_VARIANT.platforms],
            [
                "ios",
                "ios-simulator",
                "macos",
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
        self.assertIn('library(name: "NCNNVulkan", targets: ["ncnn_vulkan", "ncnn_vulkan_runtime"])', package_contents)
        self.assertIn(
            f'.package(url: "https://github.com/SPMForge/MoltenVK.git", exact: "{packaging.MOLTENVK_PACKAGE.exact_version}")',
            package_contents,
        )
        self.assertIn(
            '.binaryTarget(\n'
            '            name: "ncnn",\n'
            '            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.1/ncnn-20260113-apple.xcframework.zip",\n'
            '            checksum: "cpu-checksum"\n'
            "        )",
            package_contents,
        )
        self.assertIn(
            '.binaryTarget(\n'
            '            name: "ncnn_vulkan",\n'
            '            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.1/ncnn-20260113-apple-vulkan.xcframework.zip",\n'
            '            checksum: "vulkan-checksum"\n'
            "        )",
            package_contents,
        )
        self.assertIn(
            '.target(\n'
            '            name: "ncnn_vulkan_runtime",\n'
            '            dependencies: [\n'
            '                .product(name: "MoltenVK", package: "MoltenVK"),\n'
            '            ],\n'
            '            path: "Sources/ncnn_vulkan_runtime"\n'
            "        )",
            package_contents,
        )
        self.assertNotIn("current_release.json", package_contents)
        self.assertNotIn("Foundation", package_contents)

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

    def test_renders_local_binary_targets_for_package_contract_validation(self) -> None:
        package_contents = packaging.render_local_package_swift(
            package_name="ncnn",
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

        self.assertIn(
            '.binaryTarget(\n'
            '            name: "ncnn",\n'
            '            path: "Artifacts/ncnn.xcframework"\n'
            "        )",
            package_contents,
        )
        self.assertIn(
            '.binaryTarget(\n'
            '            name: "ncnn_vulkan",\n'
            '            path: "Artifacts/ncnn_vulkan.xcframework"\n'
            "        )",
            package_contents,
        )
        self.assertIn('library(name: "NCNNVulkan", targets: ["ncnn_vulkan", "ncnn_vulkan_runtime"])', package_contents)
        self.assertIn(
            f'.package(url: "https://github.com/SPMForge/MoltenVK.git", exact: "{packaging.MOLTENVK_PACKAGE.exact_version}")',
            package_contents,
        )

    def test_build_artifact_metadata_payload_uses_schema_and_canonical_variant_fields(self) -> None:
        release = packaging.ReleaseAsset(
            variant=packaging.CPU_VARIANT,
            upstream_tag="20260113",
            package_tag="1.0.20260113-alpha.1",
            checksum="cpu-checksum",
        )

        payload = packaging.build_artifact_metadata_payload(
            release,
            artifact_path="/tmp/ncnn-20260113-apple.xcframework.zip",
        )

        self.assertEqual(payload["schema_version"], packaging.BUILD_ARTIFACT_METADATA_SCHEMA_VERSION)
        self.assertEqual(payload["target_name"], "ncnn")
        self.assertEqual(payload["product_name"], "NCNN")
        self.assertEqual(payload["module_name"], "ncnn")
        self.assertEqual(payload["asset_name"], "ncnn-20260113-apple.xcframework.zip")
        self.assertEqual(payload["artifact_path"], "/tmp/ncnn-20260113-apple.xcframework.zip")
        self.assertEqual(payload["runtime_dependency_model"], "none")
        self.assertEqual(payload["runtime_dependency_supplier"], "none")
        self.assertEqual(payload["runtime_dependencies"], [])
        self.assertEqual(payload["strong_runtime_dependencies"], [])
        self.assertEqual(payload["weak_runtime_dependencies"], [])
        self.assertEqual(payload["forbidden_runtime_dependencies"], [])
        self.assertEqual(
            payload["platforms"],
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

    def test_load_build_artifact_metadata_rejects_variant_field_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            metadata_path = Path(temporary_directory) / "ncnn.release.json"
            payload = packaging.build_artifact_metadata_payload(
                packaging.ReleaseAsset(
                    variant=packaging.CPU_VARIANT,
                    upstream_tag="20260113",
                    package_tag="1.0.20260113-alpha.1",
                    checksum="cpu-checksum",
                ),
                artifact_path="/tmp/ncnn-20260113-apple.xcframework.zip",
            )
            payload["asset_name"] = "ncnn-20260113-mismatch.xcframework.zip"
            metadata_path.write_text(json.dumps(payload))

            with self.assertRaisesRegex(ValueError, "asset_name"):
                packaging.load_build_artifact_metadata(metadata_path)

    def test_load_build_artifact_metadata_rejects_runtime_contract_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            metadata_path = Path(temporary_directory) / "ncnn_vulkan.release.json"
            payload = packaging.build_artifact_metadata_payload(
                packaging.ReleaseAsset(
                    variant=packaging.VULKAN_VARIANT,
                    upstream_tag="20260113",
                    package_tag="1.0.20260113-alpha.1",
                    checksum="vulkan-checksum",
                ),
                artifact_path="/tmp/ncnn-20260113-apple-vulkan.xcframework.zip",
            )
            payload["strong_runtime_dependencies"] = []
            metadata_path.write_text(json.dumps(payload))

            with self.assertRaisesRegex(ValueError, "strong_runtime_dependencies"):
                packaging.load_build_artifact_metadata(metadata_path)

    def test_rendered_static_manifest_is_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = Path(temporary_directory)
            package_swift = package_root / "Package.swift"
            package_swift.write_text(
                packaging.render_package_swift(
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
            )
            packaging.write_runtime_support_sources(
                package_root,
                [
                    packaging.ReleaseAsset(
                        variant=packaging.VULKAN_VARIANT,
                        upstream_tag="20260113",
                        package_tag="1.0.20260113-alpha.1",
                        checksum="vulkan-checksum",
                    )
                ],
            )

            process = subprocess.run(
                ["swift", "package", "dump-package"],
                cwd=package_root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(process.returncode, 0, msg=process.stderr)

    def test_runtime_support_sources_are_buildable_as_swiftpm_c_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = Path(temporary_directory)
            packaging.write_runtime_support_sources(
                package_root,
                [
                    packaging.ReleaseAsset(
                        variant=packaging.VULKAN_VARIANT,
                        upstream_tag="20260113",
                        package_tag="1.0.20260113-alpha.1",
                        checksum="vulkan-checksum",
                    )
                ],
            )
            (package_root / "Package.swift").write_text(
                """// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "RuntimeSupportProbe",
    products: [
        .library(name: "RuntimeSupportProbe", targets: ["ncnn_vulkan_runtime"]),
    ],
    targets: [
        .target(name: "ncnn_vulkan_runtime", path: "Sources/ncnn_vulkan_runtime"),
    ]
)
"""
            )

            process = subprocess.run(
                ["swift", "build"],
                cwd=package_root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(process.returncode, 0, msg=process.stderr)
            self.assertTrue(
                (package_root / "Sources" / "ncnn_vulkan_runtime" / "include" / "ncnn_vulkan_runtime.h").is_file()
            )


class RootManifestTests(unittest.TestCase):
    def test_root_manifest_matches_current_release_metadata(self) -> None:
        payload = json.loads(CURRENT_RELEASE_METADATA_PATH.read_text())
        releases = [
            packaging.release_asset_from_current_release_record(release)
            for release in payload["releases"]
        ]

        expected_manifest = packaging.render_package_swift(
            package_name=payload["package_name"],
            owner=payload["owner"],
            repo=payload["repo"],
            releases=releases,
        )

        self.assertEqual(PACKAGE_SWIFT_PATH.read_text(), expected_manifest)

    def _write_manifest_fixture(self, package_root: Path) -> None:
        shutil.copy2(PACKAGE_SWIFT_PATH, package_root / "Package.swift")
        shutil.copytree(REPO_ROOT / "Sources", package_root / "Sources")

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

    def test_root_manifest_does_not_require_release_metadata_sidecar_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = Path(temporary_directory)
            self._write_manifest_fixture(package_root)

            process = self._dump_package(package_root)

            self.assertEqual(process.returncode, 0, msg=process.stderr)


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
            main_cpp = (package_root / "Smoke" / "main.cpp").read_text()
            self.assertIn('.binaryTarget(name: "ncnn", path: "Artifacts/ncnn.xcframework")', manifest)
            self.assertNotIn(str(xcframework_path), manifest)
            self.assertTrue((package_root / "Artifacts" / "ncnn.xcframework" / "Info.plist").exists())
            self.assertIn("#include <ncnn/net.h>", main_cpp)


class HeaderStagingTests(unittest.TestCase):
    def test_stage_headers_rewrites_same_framework_includes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            install_dir = temporary_root / "install"
            headers_root = install_dir / "include" / "ncnn"
            headers_root.mkdir(parents=True)
            (headers_root / "mat.h").write_text("// mat header\n")
            (headers_root / "layer.h").write_text("// layer header\n")
            (headers_root / "net.h").write_text(
                '#include "mat.h"\n'
                '#import "layer.h"\n'
                "#include <mat.h>\n"
                "#include <wrong/layer.h>\n"
                "#include <vector>\n"
            )

            staged_headers = build_apple_xcframework._stage_headers(
                install_dir,
                temporary_root / "staging",
                "ncnn_vulkan",
            )

            self.assertEqual(staged_headers, temporary_root / "staging" / "Headers")
            staged_net_header = (staged_headers / "net.h").read_text()
            self.assertIn("#include <ncnn_vulkan/mat.h>", staged_net_header)
            self.assertIn("#import <ncnn_vulkan/layer.h>", staged_net_header)
            self.assertNotIn("#include <mat.h>", staged_net_header)
            self.assertNotIn("#include <wrong/layer.h>", staged_net_header)
            self.assertIn("#include <ncnn_vulkan/layer.h>", staged_net_header)
            self.assertIn("#include <vector>", staged_net_header)

    def test_vulkan_stage_headers_rewrites_vulkan_sdk_include_to_moltenvk_framework(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            install_dir = temporary_root / "install"
            headers_root = install_dir / "include" / "ncnn"
            headers_root.mkdir(parents=True)
            (headers_root / "platform.h").write_text(
                "#include <vulkan/vulkan.h>\n"
                "#include <vector>\n"
            )

            staged_headers = build_apple_xcframework._stage_headers(
                install_dir,
                temporary_root / "staging",
                "ncnn_vulkan",
                external_framework_include_rewrites=build_apple_xcframework._external_framework_include_rewrites_for_variant(
                    packaging.VULKAN_VARIANT
                ),
            )

            staged_platform_header = (staged_headers / "platform.h").read_text()
            self.assertIn("#include <MoltenVK/vulkan/vulkan.h>", staged_platform_header)
            self.assertNotIn("#include <vulkan/vulkan.h>", staged_platform_header)
            self.assertIn("#include <vector>", staged_platform_header)


class ValidationWorkflowHelperTests(unittest.TestCase):
    def _write_release_archive_fixture(self, root: Path, variant: packaging.Variant, upstream_tag: str) -> Path:
        payload_root = root / "payload"
        xcframework_root = payload_root / f"{variant.target_name}.xcframework"
        xcframework_root.mkdir(parents=True)
        (xcframework_root / "Info.plist").write_text("fixture")

        archive_path = root / packaging.asset_name_for_variant(variant, upstream_tag)
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.write(
                xcframework_root / "Info.plist",
                arcname=f"{variant.target_name}.xcframework/Info.plist",
            )
        return archive_path

    def _archive_checksum(self, archive_path: Path) -> str:
        return hashlib.sha256(archive_path.read_bytes()).hexdigest()

    def test_validate_package_contract_vulkan_consumer_includes_gpu_header(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            release_input = validate_package_contract.ValidationReleaseInput(
                metadata_path=temporary_root / "ncnn_vulkan.release.json",
                archive_path=temporary_root / "ncnn-20260113-apple-vulkan.xcframework.zip",
                build_metadata=packaging.BuildArtifactMetadata(
                    release_asset=packaging.ReleaseAsset(
                        variant=packaging.VULKAN_VARIANT,
                        upstream_tag="20260113",
                        package_tag="1.0.20260113-alpha.1",
                        checksum="vulkan-checksum",
                    ),
                    artifact_path="/tmp/ncnn-20260113-apple-vulkan.xcframework.zip",
                ),
            )

            validate_package_contract._write_consumer_package(
                consumer_root=temporary_root / "consumer",
                local_package_root=temporary_root / "local-package",
                package_name="ncnn",
                release_input=release_input,
            )

            main_cpp = (temporary_root / "consumer" / "Smoke" / "main.cpp").read_text()
            self.assertIn("#include <ncnn_vulkan/net.h>", main_cpp)
            self.assertIn("#include <ncnn_vulkan/gpu.h>", main_cpp)
            self.assertIn("ncnn::get_gpu_count()", main_cpp)

    def test_validate_package_contract_requires_vulkan_strong_moltenvk_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            cpu_archive_path = self._write_release_archive_fixture(
                temporary_root / "cpu",
                packaging.CPU_VARIANT,
                "20260113",
            )
            vulkan_archive_path = self._write_release_archive_fixture(
                temporary_root / "vulkan",
                packaging.VULKAN_VARIANT,
                "20260113",
            )
            cpu_metadata_path = temporary_root / "ncnn.release.json"
            vulkan_metadata_path = temporary_root / "ncnn_vulkan.release.json"
            cpu_metadata_path.write_text(
                json.dumps(
                    packaging.build_artifact_metadata_payload(
                        packaging.ReleaseAsset(
                            variant=packaging.CPU_VARIANT,
                            upstream_tag="20260113",
                            package_tag="1.0.20260113-alpha.1",
                            checksum=self._archive_checksum(cpu_archive_path),
                        ),
                        artifact_path=str(cpu_archive_path),
                    )
                )
            )
            vulkan_metadata_path.write_text(
                json.dumps(
                    packaging.build_artifact_metadata_payload(
                        packaging.ReleaseAsset(
                            variant=packaging.VULKAN_VARIANT,
                            upstream_tag="20260113",
                            package_tag="1.0.20260113-alpha.1",
                            checksum=self._archive_checksum(vulkan_archive_path),
                        ),
                        artifact_path=str(vulkan_archive_path),
                    )
                )
            )
            release_inputs = validate_package_contract._load_release_inputs(
                [cpu_metadata_path, vulkan_metadata_path],
                [cpu_archive_path, vulkan_archive_path],
            )

            with mock.patch.object(
                validate_package_contract.validate_mergeable_xcframework,
                "validate_xcframework",
                return_value={"issues": []},
            ) as validate_xcframework:
                validate_package_contract._validate_release_archives(release_inputs)

            self.assertEqual(validate_xcframework.call_count, 2)
            cpu_call, vulkan_call = validate_xcframework.call_args_list
            self.assertEqual(cpu_call.kwargs["require_dependencies"], [])
            self.assertEqual(cpu_call.kwargs["require_strong_dependencies"], [])
            self.assertEqual(cpu_call.kwargs["require_weak_dependencies"], [])
            self.assertEqual(cpu_call.kwargs["forbid_dependencies"], [])
            self.assertEqual(vulkan_call.kwargs["require_dependencies"], ["@rpath/MoltenVK.framework/MoltenVK"])
            self.assertEqual(vulkan_call.kwargs["require_strong_dependencies"], ["@rpath/MoltenVK.framework/MoltenVK"])
            self.assertEqual(vulkan_call.kwargs["require_weak_dependencies"], [])
            self.assertEqual(
                vulkan_call.kwargs["forbid_dependencies"],
                ["@rpath/libvulkan.dylib", "@rpath/libvulkan.1.dylib"],
            )

    def test_validate_package_contract_accepts_fresh_release_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            cpu_metadata_path = temporary_root / "ncnn.release.json"
            cpu_metadata_path.write_text(
                json.dumps(
                    packaging.build_artifact_metadata_payload(
                        packaging.ReleaseAsset(
                            variant=packaging.CPU_VARIANT,
                            upstream_tag="20260113",
                            package_tag="1.0.20260113-alpha.1",
                            checksum=self._archive_checksum(
                                self._write_release_archive_fixture(
                                    temporary_root / "cpu",
                                    packaging.CPU_VARIANT,
                                    "20260113",
                                )
                            ),
                        ),
                        artifact_path="/tmp/ncnn-20260113-apple.xcframework.zip",
                    )
                )
            )
            vulkan_metadata_path = temporary_root / "ncnn_vulkan.release.json"
            vulkan_metadata_path.write_text(
                json.dumps(
                    packaging.build_artifact_metadata_payload(
                        packaging.ReleaseAsset(
                            variant=packaging.VULKAN_VARIANT,
                            upstream_tag="20260113",
                            package_tag="1.0.20260113-alpha.1",
                            checksum=self._archive_checksum(
                                self._write_release_archive_fixture(
                                    temporary_root / "vulkan",
                                    packaging.VULKAN_VARIANT,
                                    "20260113",
                                )
                            ),
                        ),
                        artifact_path="/tmp/ncnn-20260113-apple-vulkan.xcframework.zip",
                    )
                )
            )
            cpu_archive_path = temporary_root / "cpu" / packaging.asset_name_for_variant(packaging.CPU_VARIANT, "20260113")
            vulkan_archive_path = temporary_root / "vulkan" / packaging.asset_name_for_variant(packaging.VULKAN_VARIANT, "20260113")

            with (
                mock.patch.object(validate_package_contract, "_validate_release_archives", return_value=[{}, {}]) as validate_archives,
                mock.patch.object(validate_package_contract, "_validate_manifest") as validate_manifest,
            ):
                observed: dict[str, object] = {}

                def _capture_consumer_inputs(
                    local_package_root: Path,
                    package_name: str,
                    release_inputs: list[validate_package_contract.ValidationReleaseInput],
                ) -> None:
                    observed["package_name"] = package_name
                    observed["release_count"] = len(release_inputs)
                    observed["manifest"] = (local_package_root / "Package.swift").read_text()
                    observed["cpu_artifact_exists"] = (
                        local_package_root / "Artifacts" / "ncnn.xcframework" / "Info.plist"
                    ).exists()
                    observed["vulkan_artifact_exists"] = (
                        local_package_root / "Artifacts" / "ncnn_vulkan.xcframework" / "Info.plist"
                    ).exists()

                with mock.patch.object(
                    validate_package_contract,
                    "_validate_local_package_consumers",
                    side_effect=_capture_consumer_inputs,
                ) as validate_consumers:
                    stdout = io.StringIO()
                    with mock.patch("sys.stdout", stdout):
                        exit_code = validate_package_contract.main(
                            [
                                "--repo-root",
                                str(REPO_ROOT),
                                "--release-metadata",
                                str(cpu_metadata_path),
                                "--release-metadata",
                                str(vulkan_metadata_path),
                                "--release-archive",
                                str(cpu_archive_path),
                                "--release-archive",
                                str(vulkan_archive_path),
                            ]
                        )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["release_count"], 2)
            self.assertEqual(payload["archive_validation_count"], 2)
            self.assertEqual(payload["consumer_validation_count"], 2)
            validate_archives.assert_called_once()
            validate_manifest.assert_called_once()
            validate_consumers.assert_called_once()
            self.assertEqual(observed["package_name"], "ncnn")
            self.assertEqual(observed["release_count"], 2)
            self.assertIn('path: "Artifacts/ncnn.xcframework"', observed["manifest"])
            self.assertIn('path: "Artifacts/ncnn_vulkan.xcframework"', observed["manifest"])
            self.assertIn('.product(name: "MoltenVK", package: "MoltenVK")', observed["manifest"])
            self.assertTrue(observed["cpu_artifact_exists"])
            self.assertTrue(observed["vulkan_artifact_exists"])

    def test_validate_package_contract_applies_package_tag_override_to_rendered_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            cpu_archive_path = self._write_release_archive_fixture(
                temporary_root / "cpu",
                packaging.CPU_VARIANT,
                "20260113",
            )
            cpu_metadata_path = temporary_root / "ncnn.release.json"
            cpu_metadata_path.write_text(
                json.dumps(
                    packaging.build_artifact_metadata_payload(
                        packaging.ReleaseAsset(
                            variant=packaging.CPU_VARIANT,
                            upstream_tag="20260113",
                            package_tag="1.0.20260113-alpha.1",
                            checksum=self._archive_checksum(cpu_archive_path),
                        ),
                        artifact_path=str(cpu_archive_path),
                    )
                )
            )
            vulkan_archive_path = self._write_release_archive_fixture(
                temporary_root / "vulkan",
                packaging.VULKAN_VARIANT,
                "20260113",
            )
            vulkan_metadata_path = temporary_root / "ncnn_vulkan.release.json"
            vulkan_metadata_path.write_text(
                json.dumps(
                    packaging.build_artifact_metadata_payload(
                        packaging.ReleaseAsset(
                            variant=packaging.VULKAN_VARIANT,
                            upstream_tag="20260113",
                            package_tag="1.0.20260113-alpha.1",
                            checksum=self._archive_checksum(vulkan_archive_path),
                        ),
                        artifact_path=str(vulkan_archive_path),
                    )
                )
            )

            observed: dict[str, str] = {}
            with (
                mock.patch.object(validate_package_contract, "_validate_release_archives", return_value=[{}, {}]),
                mock.patch.object(validate_package_contract, "_validate_manifest"),
                mock.patch.object(validate_package_contract, "_validate_local_package_consumers"),
                mock.patch.object(validate_package_contract, "_stage_local_release_archives", return_value=temporary_root / "Artifacts"),
            ):
                original_render = validate_package_contract._render_release_metadata

                def _capture_render(*args, **kwargs):
                    current_release_json = original_render(*args, **kwargs)
                    package_root = kwargs["package_root"] if "package_root" in kwargs else args[0]
                    observed["manifest"] = (package_root / "Package.swift").read_text()
                    observed["current_release_json"] = current_release_json.read_text()
                    return current_release_json

                with mock.patch.object(validate_package_contract, "_render_release_metadata", side_effect=_capture_render):
                    exit_code = validate_package_contract.main(
                        [
                            "--repo-root",
                            str(REPO_ROOT),
                            "--package-tag-override",
                            "1.0.20260113-alpha.2",
                            "--release-metadata",
                            str(cpu_metadata_path),
                            "--release-metadata",
                            str(vulkan_metadata_path),
                            "--release-archive",
                            str(cpu_archive_path),
                            "--release-archive",
                            str(vulkan_archive_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            self.assertIn("1.0.20260113-alpha.2", observed["manifest"])
            self.assertIn("1.0.20260113-alpha.2", observed["current_release_json"])

    def test_validate_package_contract_rejects_missing_release_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            cpu_metadata_path = temporary_root / "ncnn.release.json"
            cpu_metadata_path.write_text(
                json.dumps(
                    packaging.build_artifact_metadata_payload(
                        packaging.ReleaseAsset(
                            variant=packaging.CPU_VARIANT,
                            upstream_tag="20260113",
                            package_tag="1.0.20260113-alpha.1",
                            checksum="cpu-checksum",
                        ),
                        artifact_path="/tmp/ncnn-20260113-apple.xcframework.zip",
                    )
                )
            )

            stderr = io.StringIO()
            with mock.patch("sys.stderr", stderr):
                exit_code = validate_package_contract.main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "--release-metadata",
                        str(cpu_metadata_path),
                        "--release-archive",
                        str(temporary_root / "missing" / "ncnn-20260113-apple.xcframework.zip"),
                    ]
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("missing release archive", stderr.getvalue())

    def test_validate_package_contract_rejects_checksum_drift_between_metadata_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            cpu_archive_path = self._write_release_archive_fixture(
                temporary_root / "cpu",
                packaging.CPU_VARIANT,
                "20260113",
            )
            cpu_metadata_path = temporary_root / "ncnn.release.json"
            cpu_metadata_path.write_text(
                json.dumps(
                    packaging.build_artifact_metadata_payload(
                        packaging.ReleaseAsset(
                            variant=packaging.CPU_VARIANT,
                            upstream_tag="20260113",
                            package_tag="1.0.20260113-alpha.1",
                            checksum="0" * 64,
                        ),
                        artifact_path="/tmp/ncnn-20260113-apple.xcframework.zip",
                    )
                )
            )

            stderr = io.StringIO()
            with (
                mock.patch.object(validate_package_contract, "_validate_manifest"),
                mock.patch.object(validate_package_contract, "_validate_local_package_consumers"),
                mock.patch("sys.stderr", stderr),
            ):
                exit_code = validate_package_contract.main(
                    [
                        "--repo-root",
                        str(REPO_ROOT),
                        "--release-metadata",
                        str(cpu_metadata_path),
                        "--release-archive",
                        str(cpu_archive_path),
                    ]
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("checksum mismatch", stderr.getvalue())

    def test_validate_package_contract_formats_subprocess_errors(self) -> None:
        error = subprocess.CalledProcessError(
            2,
            ["swift", "package", "dump-package"],
            output="manifest stdout\n",
            stderr="manifest stderr\n",
        )

        message = validate_package_contract._describe_subprocess_error(error)

        self.assertIn("command failed with exit code 2", message)
        self.assertIn("swift package dump-package", message)
        self.assertIn("stdout:\nmanifest stdout", message)
        self.assertIn("stderr:\nmanifest stderr", message)

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


class SopConformanceTests(unittest.TestCase):
    def test_rejects_hardcoded_deployment_targets_in_production_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            repo_root = temporary_root / "repo"
            target_dir = repo_root / "scripts" / "spm"
            target_dir.mkdir(parents=True)
            shutil.copy2(PLATFORM_METADATA_PATH, target_dir / "platforms.json")

            hardcoded_script = target_dir / "build_apple_xcframework.py"
            hardcoded_script.write_text('command.append("-DDEPLOYMENT_TARGET=13.0")\n')

            with self.assertRaisesRegex(
                SystemExit,
                "must stay centralized in scripts/spm/platforms.json",
            ):
                verify_sop_conformance._assert_no_hardcoded_deployment_targets(
                    repo_root,
                    (hardcoded_script,),
                )


class BuildCommandTests(unittest.TestCase):
    def test_resolve_package_tag_prefers_explicit_value(self) -> None:
        arguments = argparse.Namespace(upstream_tag="20260113", package_tag="1.0.20260113-alpha.2")

        self.assertEqual(build_apple_xcframework._resolve_package_tag(arguments), "1.0.20260113-alpha.2")

    def test_resolve_package_tag_defaults_to_alpha_1_when_no_override_is_provided(self) -> None:
        arguments = argparse.Namespace(upstream_tag="20260113", package_tag=None)

        self.assertEqual(
            build_apple_xcframework._resolve_package_tag(arguments),
            "1.0.20260113-alpha.1",
        )

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

    def test_vulkan_cmake_configure_strong_links_moltenvk_and_disables_simplevk(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            moltenvk_xcframework = temporary_root / "MoltenVK.xcframework"
            framework_root = moltenvk_xcframework / "ios-arm64" / "MoltenVK.framework"
            moltenvk_include_dir = temporary_root / "MoltenVKHeaders" / "include"
            (moltenvk_include_dir / "vulkan").mkdir(parents=True)
            (moltenvk_include_dir / "MoltenVK" / "vulkan").mkdir(parents=True)
            (moltenvk_include_dir / "vulkan" / "vulkan.h").write_text("#include <MoltenVK/vulkan/vk_platform.h>\n")
            (moltenvk_include_dir / "MoltenVK" / "vulkan" / "vk_platform.h").write_text("// vk_platform\n")
            framework_root.mkdir(parents=True)
            (framework_root / "MoltenVK").write_text("binary")
            (moltenvk_xcframework / "Info.plist").write_bytes(
                plistlib.dumps(
                    {
                        "AvailableLibraries": [
                            {
                                "LibraryIdentifier": "ios-arm64",
                                "LibraryPath": "MoltenVK.framework",
                                "SupportedArchitectures": ["arm64"],
                                "SupportedPlatform": "ios",
                            }
                        ]
                    }
                )
            )

            command = build_apple_xcframework._cmake_configure_command(
                packaging.VULKAN_VARIANT,
                packaging.VULKAN_VARIANT.platforms[0],
                source_root=Path("/tmp/source"),
                build_dir=temporary_root / "build",
                install_dir=Path("/tmp/install"),
                moltenvk_xcframework=moltenvk_xcframework,
                moltenvk_include_dir=moltenvk_include_dir,
            )

            self.assertIn("-DNCNN_VULKAN=ON", command)
            self.assertIn("-DNCNN_SIMPLEVK=OFF", command)
            self.assertIn(f"-DVulkan_LIBRARY={framework_root / 'MoltenVK'}", command)
            self.assertIn(f"-DVulkan_INCLUDE_DIR={moltenvk_include_dir.resolve()}", command)
            self.assertFalse((temporary_root / "build" / "moltenvk-include").exists())

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

    def test_stage_framework_bundle_creates_flat_ios_layout(self) -> None:
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
                    platform=packaging.CPU_VARIANT.platforms[0],
                    environment={"PATH": "/usr/bin:/bin"},
                )

            self.assertEqual(framework_path, temporary_root / "staging" / "ncnn.framework")
            self.assertTrue((framework_path / "ncnn").exists())
            self.assertTrue((framework_path / "Headers" / "net.h").exists())
            self.assertTrue((framework_path / "Modules" / "module.modulemap").exists())
            self.assertTrue((framework_path / "Info.plist").exists())
            self.assertFalse((framework_path / "Versions").exists())
            run_mock.assert_called_once_with(
                [
                    "install_name_tool",
                    "-id",
                    "@rpath/ncnn.framework/ncnn",
                    str(framework_path / "ncnn"),
                ],
                env={"PATH": "/usr/bin:/bin"},
            )

    def test_stage_framework_bundle_skips_install_name_rewrite_for_watchos_arm64_32(self) -> None:
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
                    platform=packaging.CPU_VARIANT.platforms[6],
                    environment={"PATH": "/usr/bin:/bin"},
                )

            self.assertEqual(framework_path, temporary_root / "staging" / "ncnn.framework")
            self.assertTrue((framework_path / "ncnn").exists())
            self.assertTrue((framework_path / "Headers" / "net.h").exists())
            self.assertTrue((framework_path / "Modules" / "module.modulemap").exists())
            run_mock.assert_not_called()

    def test_create_xcframework_accepts_framework_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            staged_framework = temporary_root / "ios.framework"
            staged_framework.mkdir()
            staged_macos_framework = temporary_root / "macos.framework"
            staged_macos_framework.mkdir()

            with mock.patch.object(build_apple_xcframework, "_run") as run_mock:
                output_path = build_apple_xcframework._create_xcframework(
                    variant=packaging.CPU_VARIANT,
                    staged_frameworks=[staged_framework, staged_macos_framework],
                    output_dir=temporary_root,
                    environment={"PATH": "/usr/bin:/bin"},
                )

            self.assertEqual(output_path, temporary_root / "ncnn.xcframework")
            run_mock.assert_called_once_with(
                [
                    "xcodebuild",
                    "-create-xcframework",
                    "-framework",
                    str(staged_framework),
                    "-framework",
                    str(staged_macos_framework),
                    "-output",
                    str(temporary_root / "ncnn.xcframework"),
                ],
                env={"PATH": "/usr/bin:/bin"},
            )

    def test_vulkan_xcframework_validation_requires_strong_moltenvk_dependency(self) -> None:
        with mock.patch(
            "scripts.spm.build_apple_xcframework.validate_mergeable_xcframework.validate_xcframework"
        ) as validate_mock:
            validate_mock.return_value = {"issues": []}

            build_apple_xcframework._validate_xcframework(
                Path("/tmp/ncnn_vulkan.xcframework"),
                packaging.VULKAN_VARIANT,
            )

            validate_mock.assert_called_once_with(
                Path("/tmp/ncnn_vulkan.xcframework"),
                [platform.swiftpm_platform for platform in packaging.VULKAN_VARIANT.platforms],
                require_dependencies=["@rpath/MoltenVK.framework/MoltenVK"],
                require_strong_dependencies=["@rpath/MoltenVK.framework/MoltenVK"],
                require_weak_dependencies=[],
                forbid_dependencies=["@rpath/libvulkan.dylib", "@rpath/libvulkan.1.dylib"],
            )

    def test_cpu_xcframework_validation_does_not_require_runtime_dependency(self) -> None:
        with mock.patch(
            "scripts.spm.build_apple_xcframework.validate_mergeable_xcframework.validate_xcframework"
        ) as validate_mock:
            validate_mock.return_value = {"issues": []}

            build_apple_xcframework._validate_xcframework(
                Path("/tmp/ncnn.xcframework"),
                packaging.CPU_VARIANT,
            )

            validate_mock.assert_called_once_with(
                Path("/tmp/ncnn.xcframework"),
                [platform.swiftpm_platform for platform in packaging.CPU_VARIANT.platforms],
                require_dependencies=[],
                require_strong_dependencies=[],
                require_weak_dependencies=[],
                forbid_dependencies=[],
            )


if __name__ == "__main__":
    unittest.main()
