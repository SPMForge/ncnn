from pathlib import Path
import plistlib
import tempfile
import unittest

from scripts.spm import validate_mergeable_xcframework


class XCFrameworkValidationTests(unittest.TestCase):
    def _write_xcframework(
        self,
        root: Path,
        *,
        libraries: list[dict[str, object]],
    ) -> Path:
        xcframework_path = root / "ncnn.xcframework"
        xcframework_path.mkdir(parents=True)
        info_path = xcframework_path / "Info.plist"
        info_path.write_bytes(
            plistlib.dumps(
                {
                    "AvailableLibraries": libraries,
                    "CFBundlePackageType": "XFWK",
                    "XCFrameworkFormatVersion": "1.0",
                }
            )
        )
        return xcframework_path

    def test_reports_missing_mergeable_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            xcframework_path = self._write_xcframework(
                temporary_root,
                libraries=[
                    {
                        "LibraryIdentifier": "ios-arm64",
                        "BinaryPath": "libncnn.dylib",
                        "SupportedArchitectures": ["arm64"],
                        "SupportedPlatform": "ios",
                    }
                ],
            )
            slice_root = xcframework_path / "ios-arm64"
            slice_root.mkdir()
            (slice_root / "libncnn.dylib").write_bytes(b"binary")

            result = validate_mergeable_xcframework.validate_xcframework(xcframework_path, ["ios"])

            self.assertIn("ios: missing MergeableMetadata", result["issues"])

    def test_reports_missing_required_platform(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            xcframework_path = self._write_xcframework(
                temporary_root,
                libraries=[
                    {
                        "LibraryIdentifier": "macos-arm64_x86_64",
                        "BinaryPath": "libncnn.dylib",
                        "MergeableMetadata": True,
                        "SupportedArchitectures": ["arm64", "x86_64"],
                        "SupportedPlatform": "macos",
                    }
                ],
            )
            slice_root = xcframework_path / "macos-arm64_x86_64"
            slice_root.mkdir()
            (slice_root / "libncnn.dylib").write_bytes(b"binary")

            result = validate_mergeable_xcframework.validate_xcframework(xcframework_path, ["ios", "macos"])

            self.assertIn("missing required platform ios", result["issues"])


if __name__ == "__main__":
    unittest.main()
