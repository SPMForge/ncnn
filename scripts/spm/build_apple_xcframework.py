#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.spm import archive_builder
from scripts.spm import packaging
from scripts.spm import validate_mergeable_xcframework


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a mergeable Apple XCFramework for ncnn.")
    parser.add_argument("--variant", required=True, choices=sorted(packaging.VARIANTS_BY_TARGET))
    parser.add_argument("--upstream-tag", required=True)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--developer-dir", help="Optional Xcode developer dir override.")
    parser.add_argument("--skip-smoke-test", action="store_true")
    return parser.parse_args()


def _run(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, check=True, cwd=cwd, env=env)


def _capture_output(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    process = subprocess.run(command, check=True, cwd=cwd, env=env, capture_output=True, text=True)
    return process.stdout.strip()


def _base_environment(arguments: argparse.Namespace) -> dict[str, str]:
    environment = dict(os.environ)
    if arguments.developer_dir:
        environment["DEVELOPER_DIR"] = arguments.developer_dir
    return environment


def _compiler_launcher_flags() -> list[str]:
    ccache_path = os.environ.get("CCACHE_BIN") or shutil.which("ccache")
    if not ccache_path:
        return []
    return [
        f"-DCMAKE_C_COMPILER_LAUNCHER={ccache_path}",
        f"-DCMAKE_CXX_COMPILER_LAUNCHER={ccache_path}",
    ]


def _cmake_configure_command(
    variant: packaging.Variant,
    platform: packaging.Platform,
    source_root: Path,
    build_dir: Path,
    install_dir: Path,
) -> list[str]:
    command = [
        "cmake",
        "-S",
        str(source_root),
        "-B",
        str(build_dir),
        "-G",
        "Xcode",
        f"-DCMAKE_TOOLCHAIN_FILE={packaging.TOOLCHAIN_FILE}",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        f"-DPLATFORM={platform.cmake_platform}",
        f"-DARCHS={';'.join(platform.archs)}",
        f"-DDEPLOYMENT_TARGET={platform.deployment_target}",
        "-DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED=NO",
        "-DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_REQUIRED=NO",
        "-DCMAKE_XCODE_ATTRIBUTE_CODE_SIGN_STYLE=Manual",
        "-DNCNN_SHARED_LIB=ON",
        "-DNCNN_OPENMP=ON",
        "-DNCNN_SIMPLEOMP=ON",
        "-DNCNN_BUILD_TOOLS=OFF",
        "-DNCNN_BUILD_EXAMPLES=OFF",
        "-DNCNN_BUILD_BENCHMARK=OFF",
        "-DNCNN_BUILD_TESTS=OFF",
        "-DNCNN_INSTALL_SDK=ON",
        *_compiler_launcher_flags(),
    ]

    if variant is packaging.VULKAN_VARIANT:
        command.append("-DNCNN_VULKAN=ON")
    else:
        command.append("-DNCNN_VULKAN=OFF")

    return command


def _build_command(build_dir: Path) -> list[str]:
    return [
        "cmake",
        "--build",
        str(build_dir),
        "--config",
        "Release",
        "--target",
        "install",
        "--",
        "CODE_SIGNING_ALLOWED=NO",
        "CODE_SIGNING_REQUIRED=NO",
        "CODE_SIGN_STYLE=Manual",
    ]


def _archive_command(build_dir: Path, archive_path: Path, derived_data_path: Path, platform: packaging.Platform) -> list[str]:
    return [
        "xcodebuild",
        "archive",
        "-project",
        str(build_dir / "ncnn.xcodeproj"),
        "-scheme",
        "ncnn",
        "-configuration",
        "Release",
        "-destination",
        platform.xcode_destination,
        "-archivePath",
        str(archive_path),
        "-derivedDataPath",
        str(derived_data_path),
        f"ARCHS={' '.join(platform.archs)}",
        "SKIP_INSTALL=NO",
        "CODE_SIGNING_ALLOWED=NO",
        "CODE_SIGNING_REQUIRED=NO",
        "CODE_SIGN_STYLE=Manual",
        "MERGEABLE_LIBRARY=YES",
        "ONLY_ACTIVE_ARCH=NO",
    ]


def _ensure_vulkan_sources(source_root: Path) -> None:
    glslang_cmakelists = source_root / "glslang" / "CMakeLists.txt"
    if not glslang_cmakelists.exists():
        raise FileNotFoundError(
            f"glslang submodule is missing at {glslang_cmakelists}. Run git submodule update --init --recursive."
        )


def _stage_headers(install_dir: Path, output_dir: Path, module_name: str) -> Path:
    headers_source = install_dir / "include" / "ncnn"
    if not headers_source.exists():
        raise FileNotFoundError(f"public headers not found at {headers_source}")

    headers_output = output_dir / "Headers"
    if headers_output.exists():
        shutil.rmtree(headers_output)
    shutil.copytree(headers_source, headers_output)
    (headers_output / "module.modulemap").write_text(
        f"""module {module_name} {{
    umbrella "."
    export *
    module * {{ export * }}
}}
"""
    )
    return headers_output


def _should_rewrite_install_name(platform: packaging.Platform) -> bool:
    return "arm64_32" not in platform.archs


def _stage_dynamic_library(
    source_binary: Path,
    output_dir: Path,
    target_name: str,
    platform: packaging.Platform,
    environment: dict[str, str],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    staged_binary = output_dir / f"lib{target_name}.dylib"
    shutil.copy2(source_binary, staged_binary)
    if _should_rewrite_install_name(platform):
        _run(["install_name_tool", "-id", f"@rpath/{staged_binary.name}", str(staged_binary)], env=environment)
    return staged_binary


def _create_xcframework(
    variant: packaging.Variant,
    headers_path: Path,
    staged_binaries: list[Path],
    output_dir: Path,
    environment: dict[str, str],
) -> Path:
    xcframework_path = output_dir / f"{variant.target_name}.xcframework"
    if xcframework_path.exists():
        shutil.rmtree(xcframework_path)

    command = ["xcodebuild", "-create-xcframework"]
    for staged_binary in staged_binaries:
        command.extend(["-library", str(staged_binary), "-headers", str(headers_path)])
    command.extend(["-output", str(xcframework_path)])
    _run(command, env=environment)
    return xcframework_path


def _zip_xcframework(xcframework_path: Path, zip_path: Path, environment: dict[str, str]) -> None:
    if zip_path.exists():
        zip_path.unlink()
    _run(
        [
            "ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(xcframework_path),
            str(zip_path),
        ],
        env=environment,
    )


def _compute_checksum(zip_path: Path, environment: dict[str, str]) -> str:
    return _capture_output(["swift", "package", "compute-checksum", str(zip_path)], cwd=zip_path.parent, env=environment)


def _write_release_metadata(
    output_path: Path,
    variant: packaging.Variant,
    upstream_tag: str,
    package_tag: str,
    checksum: str,
    zip_path: Path,
) -> None:
    payload = {
        "target_name": variant.target_name,
        "product_name": variant.product_name,
        "module_name": variant.module_name,
        "upstream_tag": upstream_tag,
        "package_tag": package_tag,
        "asset_name": packaging.asset_name_for_variant(variant, upstream_tag),
        "artifact_path": str(zip_path),
        "checksum": checksum,
        "platforms": [platform.swiftpm_platform for platform in variant.platforms],
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _validate_xcframework(xcframework_path: Path, variant: packaging.Variant) -> None:
    result = validate_mergeable_xcframework.validate_xcframework(
        xcframework_path,
        [platform.swiftpm_platform for platform in variant.platforms],
    )
    if result["issues"]:
        print(json.dumps({"xcframeworks": [result]}, indent=2), file=sys.stderr)
        raise RuntimeError(f"xcframework validation failed for {xcframework_path}")


def _build_platform_slice(
    source_root: Path,
    variant: packaging.Variant,
    platform: packaging.Platform,
    workspace_root: Path,
    environment: dict[str, str],
) -> tuple[Path, Path]:
    build_dir = workspace_root / "build" / platform.swiftpm_platform
    install_dir = build_dir / "install"
    archive_path = build_dir / f"{variant.target_name}-{platform.swiftpm_platform}.xcarchive"
    derived_data_path = build_dir / "DerivedData"

    _run(_cmake_configure_command(variant, platform, source_root, build_dir, install_dir), env=environment)
    _run(_build_command(build_dir), env=environment)
    _run(_archive_command(build_dir, archive_path, derived_data_path, platform), env=environment)

    dynamic_library = archive_builder.find_dynamic_library(
        archive_root=archive_path,
        derived_data_root=derived_data_path,
        library_basename="ncnn",
    )
    return install_dir, dynamic_library


def main() -> int:
    arguments = _parse_arguments()
    environment = _base_environment(arguments)
    source_root = arguments.source_root.resolve()
    variant = packaging.variant_for_target_name(arguments.variant)
    package_tag = packaging.package_tag_for_upstream_tag(arguments.upstream_tag)

    if variant is packaging.VULKAN_VARIANT:
        _ensure_vulkan_sources(source_root)

    workspace_root = arguments.output_dir.resolve() / variant.target_name
    if workspace_root.exists():
        shutil.rmtree(workspace_root)
    workspace_root.mkdir(parents=True)

    staged_libraries = []
    headers_path: Path | None = None
    staging_root = workspace_root / "staging"

    for platform in variant.platforms:
        install_dir, dynamic_library = _build_platform_slice(source_root, variant, platform, workspace_root, environment)
        if headers_path is None:
            headers_path = _stage_headers(install_dir, staging_root / variant.target_name, variant.module_name)
        staged_library = _stage_dynamic_library(
            dynamic_library,
            staging_root / variant.target_name / platform.swiftpm_platform,
            variant.target_name,
            platform,
            environment,
        )
        staged_libraries.append(staged_library)

    assert headers_path is not None

    xcframework_path = _create_xcframework(
        variant=variant,
        headers_path=headers_path,
        staged_binaries=staged_libraries,
        output_dir=workspace_root,
        environment=environment,
    )
    _validate_xcframework(xcframework_path, variant)

    if not arguments.skip_smoke_test:
        _run(
            [
                sys.executable,
                str(packaging.SCRIPTS_ROOT / "smoke_test_package.py"),
                "--variant",
                variant.target_name,
                "--xcframework",
                str(xcframework_path),
            ],
            env=environment,
        )

    zip_path = workspace_root / packaging.asset_name_for_variant(variant, arguments.upstream_tag)
    _zip_xcframework(xcframework_path, zip_path, environment)
    checksum = _compute_checksum(zip_path, environment)

    release_metadata_path = workspace_root / f"{variant.target_name}.release.json"
    _write_release_metadata(release_metadata_path, variant, arguments.upstream_tag, package_tag, checksum, zip_path)

    print(
        json.dumps(
            {
                "target_name": variant.target_name,
                "package_tag": package_tag,
                "upstream_tag": arguments.upstream_tag,
                "artifact_path": str(zip_path),
                "metadata_path": str(release_metadata_path),
                "checksum": checksum,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
