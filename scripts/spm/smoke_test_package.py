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
    shutil.copytree(xcframework_path.resolve(), staged_xcframework_path, symlinks=True)
    return staged_xcframework_path.relative_to(package_root)


def _write_consumer_package(package_root: Path, variant: packaging.Variant, xcframework_path: Path) -> None:
    package_root.mkdir(parents=True, exist_ok=True)
    (package_root / "Smoke").mkdir(parents=True, exist_ok=True)
    local_xcframework_path = _stage_xcframework(package_root, xcframework_path)
    release = packaging.ReleaseAsset(
        variant=variant,
        upstream_tag="00000000",
        package_tag="0.0.0-smoke",
        checksum="0" * 64,
    )
    packaging.write_runtime_support_sources(package_root, [release])

    package_dependency_lines = [
        f'        .package(url: "{dependency.url}", exact: "{dependency.exact_version}"),'
        for dependency in variant.swiftpm_dependencies
    ]
    dependency_section = ""
    if package_dependency_lines:
        dependency_section = "    dependencies: [\n" + "\n".join(package_dependency_lines) + "\n    ],\n"

    runtime_target_section = ""
    if variant.runtime_support_target is not None:
        runtime_dependencies = "\n".join(
            f'                .product(name: "{dependency.product_name}", package: "{dependency.package_name}"),'
            for dependency in variant.runtime_support_target.product_dependencies
        )
        runtime_target_section = f"""        .target(
            name: "{variant.runtime_support_target.target_name}",
            dependencies: [
{runtime_dependencies}
            ],
            path: "{variant.runtime_support_target.path}"
        ),
"""

    executable_dependencies = [f'"{variant.target_name}"']
    if variant.runtime_support_target is not None:
        executable_dependencies.append(f'"{variant.runtime_support_target.target_name}"')
    executable_dependency_list = ", ".join(executable_dependencies)

    package_swift = f"""// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "NCNNSmoke",
    platforms: [
        .macOS("{packaging.PACKAGE_PLATFORM_DEPLOYMENT_TARGETS['macos']}"),
    ],
    products: [
        .executable(name: "Smoke", targets: ["Smoke"]),
        .executable(name: "SmokeSwift", targets: ["SmokeSwift"]),
    ],
{dependency_section}\
    targets: [
        .binaryTarget(name: "{variant.target_name}", path: "{local_xcframework_path.as_posix()}"),
{runtime_target_section}\
        .executableTarget(
            name: "SmokeSwift",
            dependencies: [{executable_dependency_list}],
            path: "SmokeSwift",
            swiftSettings: [
                .interoperabilityMode(.Cxx),
            ],
            linkerSettings: [
                .unsafeFlags([
                    "-Xlinker", "-rpath", "-Xlinker", "@loader_path",
                    "-Xlinker", "-rpath", "-Xlinker", "@loader_path/PackageFrameworks",
                ]),
            ]
        ),
        .executableTarget(
            name: "Smoke",
            dependencies: [{executable_dependency_list}],
            path: "Smoke",
            linkerSettings: [
                .unsafeFlags([
                    "-Xlinker", "-rpath", "-Xlinker", "@loader_path",
                    "-Xlinker", "-rpath", "-Xlinker", "@loader_path/PackageFrameworks",
                ]),
            ]
        ),
    ],
    cxxLanguageStandard: .cxx11
)
"""

    main_swift = f"""import Foundation
import {variant.target_name}

let cpuCount = ncnn.get_cpu_count()
guard cpuCount > 0 else {{
    fatalError("ncnn CPU count check failed")
}}
let mat = ncnn_mat_create_2d(4, 4, nil)
guard let mat else {{
    fatalError("ncnn_mat_create_2d returned nil")
}}
ncnn_mat_fill_float(mat, 42.0)
guard ncnn_mat_get_w(mat) == 4 && ncnn_mat_get_h(mat) == 4 else {{
    fatalError("ncnn_mat dimensions mismatch")
}}
ncnn_mat_destroy(mat)
print("✅ [Swift SPM Consumer] {variant.target_name} verified! Apple Silicon Cores: \\(cpuCount), Version: \\(String(cString: ncnn_version()))")
"""

    if variant is packaging.VULKAN_VARIANT:
        main_cpp = f"""#include <{variant.target_name}/net.h>
#include <{variant.target_name}/gpu.h>

int main()
{{
    ncnn::Net net;
    (void)net;
    int gpu_count = ncnn::get_gpu_count();
    return gpu_count < 0 ? 2 : 0;
}}
"""
    else:
        main_cpp = f"""#include <{variant.target_name}/net.h>

int main()
{{
    ncnn::Net net;
    (void)net;
    return 0;
}}
"""

    (package_root / "Smoke").mkdir(parents=True, exist_ok=True)
    (package_root / "SmokeSwift").mkdir(parents=True, exist_ok=True)
    (package_root / "Package.swift").write_text(package_swift)
    (package_root / "SmokeSwift" / "main.swift").write_text(main_swift)
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
                "NCNNSmoke-Package",
                "-configuration",
                "Release",
                "-destination",
                "generic/platform=macOS",
                "MERGED_BINARY_TYPE=automatic",
                "build",
            ],
            package_root,
        )
        _run(["swift", "run", "-c", "debug", "SmokeSwift"], package_root)
        _run(["swift", "run", "-c", "debug", "Smoke"], package_root)
        _run(["swift", "run", "-c", "release", "SmokeSwift"], package_root)
        _run(["swift", "run", "-c", "release", "Smoke"], package_root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
