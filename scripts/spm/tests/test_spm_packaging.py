import unittest

from scripts.spm import packaging


class PackageVersionTests(unittest.TestCase):
    def test_maps_upstream_tag_to_package_tag(self) -> None:
        self.assertEqual(packaging.package_tag_for_upstream_tag("20260113"), "1.0.20260113")

    def test_rejects_invalid_upstream_tag(self) -> None:
        with self.assertRaises(ValueError):
            packaging.package_tag_for_upstream_tag("v20260113")


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
                    package_tag="1.0.20260113",
                    checksum="cpu-checksum",
                ),
                packaging.ReleaseAsset(
                    variant=packaging.VULKAN_VARIANT,
                    upstream_tag="20260113",
                    package_tag="1.0.20260113",
                    checksum="vulkan-checksum",
                ),
            ],
        )

        self.assertIn('library(name: "NCNN", targets: ["ncnn"])', package_contents)
        self.assertIn('library(name: "NCNNVulkan", targets: ["ncnn_vulkan"])', package_contents)
        self.assertIn(
            '.binaryTarget(name: "ncnn", url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113/ncnn-20260113-apple.xcframework.zip", checksum: "cpu-checksum")',
            package_contents,
        )
        self.assertIn(
            '.binaryTarget(name: "ncnn_vulkan", url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113/ncnn-20260113-apple-vulkan.xcframework.zip", checksum: "vulkan-checksum")',
            package_contents,
        )


if __name__ == "__main__":
    unittest.main()
