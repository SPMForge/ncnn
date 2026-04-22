#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import plistlib
import posixpath
import re
import shutil
import subprocess
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.spm import archive_builder
from scripts.spm import packaging
from scripts.spm import validate_mergeable_xcframework

_LOCAL_PUBLIC_HEADER_INCLUDE_PATTERN = re.compile(r'^(\s*#\s*(?:include|import)\s+)"([^"]+)"(.*)$')
_ANGLE_PUBLIC_HEADER_INCLUDE_PATTERN = re.compile(r'^(\s*#\s*(?:include|import)\s+)<([^>]+)>(.*)$')


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a mergeable Apple XCFramework for ncnn.")
    parser.add_argument("--variant", required=True, choices=sorted(packaging.VARIANTS_BY_TARGET))
    parser.add_argument("--upstream-tag", required=True)
    parser.add_argument("--package-tag", help="Optional resolved package tag override for release metadata.")
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


def _resolve_package_tag(arguments: argparse.Namespace) -> str:
    if arguments.package_tag:
        return arguments.package_tag
    return packaging.package_tag_for_upstream_tag(arguments.upstream_tag)


def _write_compiler_wrapper(wrapper_path: Path, ccache_path: str, compiler_path: str) -> None:
    wrapper_path.write_text(
        "#!/bin/sh\n"
        f'exec "{ccache_path}" "{compiler_path}" "$@"\n'
    )
    wrapper_path.chmod(0o755)


def _compiler_cache_environment(environment: dict[str, str], workspace_root: Path) -> dict[str, str]:
    ccache_path = os.environ.get("CCACHE_BIN") or shutil.which("ccache")
    if not ccache_path:
        return environment

    ccache_dir = environment.get("CCACHE_DIR")
    if ccache_dir:
        Path(ccache_dir).mkdir(parents=True, exist_ok=True)

    wrapper_root = workspace_root / ".compiler-wrappers"
    if wrapper_root.exists():
        shutil.rmtree(wrapper_root)
    wrapper_root.mkdir(parents=True)

    clang_path = _capture_output(["xcrun", "-f", "clang"], env=environment)
    clangxx_path = _capture_output(["xcrun", "-f", "clang++"], env=environment)

    clang_wrapper = wrapper_root / "clang"
    clangxx_wrapper = wrapper_root / "clang++"
    _write_compiler_wrapper(clang_wrapper, ccache_path, clang_path)
    _write_compiler_wrapper(clangxx_wrapper, ccache_path, clangxx_path)

    cached_environment = dict(environment)
    cached_environment["CC"] = str(clang_wrapper)
    cached_environment["CXX"] = str(clangxx_wrapper)
    cached_environment["OBJC"] = str(clang_wrapper)
    cached_environment["OBJCXX"] = str(clangxx_wrapper)
    cached_environment["LDPLUSPLUS"] = str(clangxx_wrapper)
    return cached_environment


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
    _rewrite_same_framework_header_includes(headers_output, module_name)
    return headers_output


def _normalize_public_header_include(current_header: Path, headers_root: Path, include_path: str) -> str | None:
    current_parent = current_header.parent.relative_to(headers_root).as_posix()
    normalized = posixpath.normpath(posixpath.join(current_parent, include_path))
    if normalized.startswith("../") or normalized == "..":
        return None
    resolved_path = headers_root / normalized
    if not resolved_path.is_file():
        return None
    return normalized


def _normalize_framework_style_include(current_header: Path, headers_root: Path, include_path: str) -> str | None:
    candidate_path = include_path.split("/", 1)[1] if "/" in include_path else include_path
    return _normalize_public_header_include(current_header, headers_root, candidate_path)


def _rewrite_same_framework_header_includes(headers_root: Path, framework_name: str) -> None:
    for header_path in sorted(headers_root.rglob("*.h")):
        rewritten_lines: list[str] = []
        changed = False
        for line in header_path.read_text().splitlines(keepends=True):
            stripped_line = line.rstrip("\r\n")
            line_ending = line[len(stripped_line) :]
            local_match = _LOCAL_PUBLIC_HEADER_INCLUDE_PATTERN.match(stripped_line)
            if local_match:
                normalized_include = _normalize_public_header_include(header_path, headers_root, local_match.group(2))
                if normalized_include is not None:
                    rewritten_lines.append(
                        f'{local_match.group(1)}<{framework_name}/{normalized_include}>{local_match.group(3)}{line_ending}'
                    )
                    changed = True
                    continue

            angle_match = _ANGLE_PUBLIC_HEADER_INCLUDE_PATTERN.match(stripped_line)
            if not angle_match:
                rewritten_lines.append(line)
                continue

            normalized_include = _normalize_framework_style_include(header_path, headers_root, angle_match.group(2))
            if normalized_include is None:
                rewritten_lines.append(line)
                continue

            rewritten_lines.append(
                f'{angle_match.group(1)}<{framework_name}/{normalized_include}>{angle_match.group(3)}{line_ending}'
            )
            changed = True

        if changed:
            header_path.write_text("".join(rewritten_lines))


def _copy_framework_headers(headers_source: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for source_path in headers_source.iterdir():
        if source_path.name == "module.modulemap":
            continue
        if source_path.is_dir():
            shutil.copytree(source_path, destination_dir / source_path.name)
            continue
        if source_path.is_file():
            shutil.copy2(source_path, destination_dir / source_path.name)


def _write_framework_module_map(module_map_path: Path, module_name: str) -> None:
    module_map_path.write_text(
        f"""framework module {module_name} {{
    umbrella "../Headers"
    export *
    module * {{ export * }}
}}
"""
    )


def _write_framework_info_plist(info_plist_path: Path, bundle_name: str) -> None:
    bundle_identifier = f"io.spmforge.{bundle_name.replace('_', '-')}"
    payload = {
        "CFBundleExecutable": bundle_name,
        "CFBundleIdentifier": bundle_identifier,
        "CFBundleName": bundle_name,
        "CFBundlePackageType": "FMWK",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
    }
    info_plist_path.write_bytes(plistlib.dumps(payload))


def _should_rewrite_install_name(platform: packaging.Platform) -> bool:
    return "arm64_32" not in platform.archs


def _stage_framework_bundle(
    source_binary: Path,
    headers_source: Path,
    output_dir: Path,
    bundle_name: str,
    module_name: str,
    platform: packaging.Platform,
    environment: dict[str, str],
) -> Path:
    framework_root = output_dir / f"{bundle_name}.framework"
    if framework_root.exists():
        shutil.rmtree(framework_root)

    if platform.swiftpm_platform == "macos":
        active_root = framework_root / "Versions" / "A"
        binary_path = active_root / bundle_name
        headers_path = active_root / "Headers"
        modules_path = active_root / "Modules"
        info_plist_path = active_root / "Resources" / "Info.plist"
        framework_root.mkdir(parents=True, exist_ok=True)
        headers_path.mkdir(parents=True, exist_ok=True)
        modules_path.mkdir(parents=True, exist_ok=True)
        info_plist_path.parent.mkdir(parents=True, exist_ok=True)
        install_name = f"@rpath/{bundle_name}.framework/Versions/A/{bundle_name}"
    else:
        binary_path = framework_root / bundle_name
        headers_path = framework_root / "Headers"
        modules_path = framework_root / "Modules"
        info_plist_path = framework_root / "Info.plist"
        headers_path.mkdir(parents=True, exist_ok=True)
        modules_path.mkdir(parents=True, exist_ok=True)
        install_name = f"@rpath/{bundle_name}.framework/{bundle_name}"

    shutil.copy2(source_binary, binary_path)
    _copy_framework_headers(headers_source, headers_path)
    _write_framework_module_map(modules_path / "module.modulemap", module_name)
    _write_framework_info_plist(info_plist_path, bundle_name)

    if platform.swiftpm_platform == "macos":
        versions_dir = framework_root / "Versions"
        (versions_dir / "Current").symlink_to("A")
        (framework_root / bundle_name).symlink_to(Path("Versions") / "Current" / bundle_name)
        (framework_root / "Headers").symlink_to(Path("Versions") / "Current" / "Headers")
        (framework_root / "Modules").symlink_to(Path("Versions") / "Current" / "Modules")
        (framework_root / "Resources").symlink_to(Path("Versions") / "Current" / "Resources")

    if _should_rewrite_install_name(platform):
        _run(["install_name_tool", "-id", install_name, str(binary_path)], env=environment)
    return framework_root


def _create_xcframework(
    variant: packaging.Variant,
    staged_frameworks: list[Path],
    output_dir: Path,
    environment: dict[str, str],
) -> Path:
    xcframework_path = output_dir / f"{variant.target_name}.xcframework"
    if xcframework_path.exists():
        shutil.rmtree(xcframework_path)

    command = ["xcodebuild", "-create-xcframework"]
    for staged_framework in staged_frameworks:
        command.extend(["-framework", str(staged_framework)])
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
    package_tag = _resolve_package_tag(arguments)

    if variant is packaging.VULKAN_VARIANT:
        _ensure_vulkan_sources(source_root)

    workspace_root = arguments.output_dir.resolve() / variant.target_name
    if workspace_root.exists():
        shutil.rmtree(workspace_root)
    workspace_root.mkdir(parents=True)
    environment = _compiler_cache_environment(environment, workspace_root)

    staged_frameworks = []
    headers_path: Path | None = None
    staging_root = workspace_root / "staging"

    for platform in variant.platforms:
        install_dir, dynamic_library = _build_platform_slice(source_root, variant, platform, workspace_root, environment)
        if headers_path is None:
            headers_path = _stage_headers(install_dir, staging_root / variant.target_name, variant.module_name)
        staged_framework = _stage_framework_bundle(
            source_binary=dynamic_library,
            headers_source=headers_path,
            output_dir=staging_root / variant.target_name / platform.swiftpm_platform,
            bundle_name=variant.target_name,
            module_name=variant.module_name,
            platform=platform,
            environment=environment,
        )
        staged_frameworks.append(staged_framework)

    assert headers_path is not None

    xcframework_path = _create_xcframework(
        variant=variant,
        staged_frameworks=staged_frameworks,
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
