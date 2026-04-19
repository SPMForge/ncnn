from pathlib import Path
import tempfile
import unittest

from scripts.spm import archive_builder
from scripts.spm import tag_selection


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


if __name__ == "__main__":
    unittest.main()
