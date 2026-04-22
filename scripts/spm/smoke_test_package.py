#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.spm import packaging


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local SwiftPM smoke test against a built XCFramework.")
    parser.add_argument("--variant", required=True, choices=sorted(packaging.VARIANTS_BY_TARGET))
    parser.add_argument("--xcframework", required=True, type=Path)
    return parser.parse_args()


def _run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, check=True, cwd=cwd)


def _stage_xcframework(package_root: Path, xcframework_path: Path) -> Path:
    artifacts_root = package_root / "Artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    staged_xcframework_path = artifacts_root / xcframework_path.name
    shutil.copytree(xcframework_path, staged_xcframework_path)
    return staged_xcframework_path.relative_to(package_root)


def _write_consumer_package(package_root: Path, variant: packaging.Variant, xcframework_path: Path) -> None:
    package_root.mkdir(parents=True, exist_ok=True)
    (package_root / "Smoke").mkdir(parents=True, exist_ok=True)
    local_xcframework_path = _stage_xcframework(package_root, xcframework_path)

    package_swift = f"""// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "NCNNSmoke",
    platforms: [
        .macOS("{packaging.PACKAGE_PLATFORM_DEPLOYMENT_TARGETS['macos']}"),
    ],
    products: [
        .executable(name: "Smoke", targets: ["Smoke"]),
    ],
    targets: [
        .binaryTarget(name: "{variant.target_name}", path: "{local_xcframework_path.as_posix()}"),
        .executableTarget(
            name: "Smoke",
            dependencies: ["{variant.target_name}"],
            path: "Smoke"
        ),
    ],
    cxxLanguageStandard: .cxx11
)
"""

    main_cpp = f"""#include <{variant.target_name}/net.h>

int main()
{{
    ncnn::Net net;
    (void)net;
    return 0;
}}
"""

    (package_root / "Package.swift").write_text(package_swift)
    (package_root / "Smoke" / "main.cpp").write_text(main_cpp)


def main() -> int:
    arguments = _parse_arguments()
    variant = packaging.variant_for_target_name(arguments.variant)

    with tempfile.TemporaryDirectory(prefix="ncnn-spm-smoke-") as temporary_directory:
        package_root = Path(temporary_directory)
        _write_consumer_package(package_root, variant, arguments.xcframework.resolve())
        _run(["swift", "build", "-c", "debug"], package_root)
        _run(["swift", "build", "-c", "release"], package_root)
        _run(
            [
                "xcodebuild",
                "-scheme",
                "NCNNSmoke",
                "-configuration",
                "Release",
                "-destination",
                "generic/platform=macOS",
                "MERGED_BINARY_TYPE=automatic",
                "build",
            ],
            package_root,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
