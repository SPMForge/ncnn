#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess


EXPECTED_VTOOL_PLATFORMS = {
    "ios": "IOS",
    "ios-simulator": "IOSSIMULATOR",
    "ios-maccatalyst": "MACCATALYST",
    "macos": "MACOS",
    "tvos": "TVOS",
    "tvos-simulator": "TVOSSIMULATOR",
    "watchos": "WATCHOS",
    "watchos-simulator": "WATCHOSSIMULATOR",
    "xros": "VISIONOS",
    "xros-simulator": "VISIONOSSIMULATOR",
}


def command_output(arguments: list[str]) -> str:
    process = subprocess.run(arguments, check=True, capture_output=True, text=True)
    return "\n".join(part for part in [process.stdout, process.stderr] if part).strip()


def _is_framework_entry(entry: dict[str, object]) -> bool:
    library_path = entry.get("LibraryPath")
    return isinstance(library_path, str) and library_path.endswith(".framework")


def _framework_binary_path(framework_path: Path) -> Path:
    framework_name = framework_path.stem
    versioned_binary_path = framework_path / "Versions" / "Current" / framework_name
    if versioned_binary_path.exists():
        return versioned_binary_path
    return framework_path / framework_name


def _has_versioned_macos_framework_layout(framework_path: Path) -> bool:
    framework_name = framework_path.stem
    versions_dir = framework_path / "Versions"
    current_link = versions_dir / "Current"
    if not versions_dir.is_dir() or not current_link.is_symlink():
        return False

    current_root = current_link.resolve()
    required_paths = [
        current_root / framework_name,
        current_root / "Headers",
        current_root / "Modules",
        current_root / "Resources",
        current_root / "Resources" / "Info.plist",
    ]
    if not all(path.exists() for path in required_paths):
        return False

    expected_top_level_targets = {
        framework_name: current_root / framework_name,
        "Headers": current_root / "Headers",
        "Modules": current_root / "Modules",
        "Resources": current_root / "Resources",
    }
    for name, expected_target in expected_top_level_targets.items():
        top_level_path = framework_path / name
        if not top_level_path.is_symlink():
            return False
        if top_level_path.resolve() != expected_target:
            return False

    return True


def platform_key(entry: dict[str, object]) -> str:
    platform = entry.get("SupportedPlatform")
    variant = entry.get("SupportedPlatformVariant")
    if not isinstance(platform, str):
        return "unknown"
    if not isinstance(variant, str):
        return platform
    return f"{platform}-{variant}"


def discover_xcframeworks(raw_paths: list[str]) -> list[Path]:
    results: list[Path] = []
    for raw_path in raw_paths:
        path = Path(raw_path).resolve()
        if not path.exists():
            raise SystemExit(f"path does not exist: {path}")
        if path.is_dir() and path.name.endswith(".xcframework"):
            results.append(path)
            continue
        if path.is_dir():
            results.extend(sorted(child for child in path.glob("*.xcframework") if child.is_dir()))
            continue
        raise SystemExit(f"unsupported path: {path}")
    if not results:
        raise SystemExit("no xcframeworks found")
    return results


def inspect_entry(xcframework_path: Path, entry: dict[str, object]) -> dict[str, object]:
    platform = platform_key(entry)
    library_identifier = entry.get("LibraryIdentifier")
    binary_path = None
    framework_path = None
    if isinstance(library_identifier, str):
        if _is_framework_entry(entry):
            framework_path = xcframework_path / library_identifier / str(entry["LibraryPath"])
            binary_path = _framework_binary_path(framework_path)
        else:
            binary_name = entry.get("BinaryPath") or entry.get("LibraryPath")
            if isinstance(binary_name, str):
                binary_path = xcframework_path / library_identifier / binary_name

    result = {
        "platform": platform,
        "architectures": entry.get("SupportedArchitectures") or [],
        "mergeable_metadata": entry.get("MergeableMetadata") is True,
        "binary_path": str(binary_path) if binary_path is not None else None,
        "binary_exists": bool(binary_path and binary_path.exists()),
    }
    if framework_path is not None:
        result["framework_path"] = str(framework_path)
        result["framework_exists"] = framework_path.exists()
        result["framework_versioned_layout"] = platform == "macos" and _has_versioned_macos_framework_layout(framework_path)

    if binary_path is not None and binary_path.exists() and shutil.which("xcrun"):
        try:
            output = command_output(["xcrun", "vtool", "-show-build", str(binary_path)])
            result["vtool_platforms"] = sorted(set(re.findall(r"platform\s+([A-Z0-9_]+)", output)))
        except subprocess.CalledProcessError as error:
            error_output = "\n".join(part for part in [error.stdout, error.stderr] if part).strip()
            result["vtool_error"] = error_output if error_output else str(error)

    return result


def inspect_xcframework(xcframework_path: Path) -> dict[str, object]:
    info_path = xcframework_path / "Info.plist"
    if not info_path.exists():
        return {
            "xcframework": str(xcframework_path),
            "issues": [f"missing Info.plist: {info_path}"],
            "entries": [],
        }

    info = plistlib.loads(info_path.read_bytes())
    available = info.get("AvailableLibraries")
    if not isinstance(available, list):
        return {
            "xcframework": str(xcframework_path),
            "issues": ["Info.plist missing AvailableLibraries"],
            "entries": [],
        }

    entries = [inspect_entry(xcframework_path, entry) for entry in available if isinstance(entry, dict)]
    issues: list[str] = []

    for entry in entries:
        platform = str(entry["platform"])
        if not entry["mergeable_metadata"]:
            issues.append(f"{platform}: missing MergeableMetadata")
        if not entry["binary_exists"]:
            issues.append(f"{platform}: missing binary at declared path")
        if platform == "macos" and "framework_path" in entry and not entry.get("framework_versioned_layout", False):
            issues.append(f"{platform}: framework bundle must use versioned macOS layout")

        expected_vtool_platform = EXPECTED_VTOOL_PLATFORMS.get(platform)
        if expected_vtool_platform is None:
            issues.append(f"{platform}: unsupported platform key")
            continue

        if "vtool_error" in entry:
            issues.append(f"{platform}: vtool inspection failed")
            continue

        vtool_platforms = entry.get("vtool_platforms")
        if isinstance(vtool_platforms, list) and vtool_platforms and expected_vtool_platform not in vtool_platforms:
            issues.append(
                f"{platform}: vtool platform mismatch, expected {expected_vtool_platform}, got {', '.join(vtool_platforms)}"
            )

    return {
        "xcframework": str(xcframework_path),
        "issues": issues,
        "entries": entries,
    }


def validate_xcframework(xcframework_path: Path, required_platforms: list[str]) -> dict[str, object]:
    result = inspect_xcframework(xcframework_path)
    available_platforms = sorted(str(entry["platform"]) for entry in result["entries"])
    missing_platforms = sorted(set(required_platforms) - set(available_platforms))
    if missing_platforms:
        result["issues"].extend(f"missing required platform {platform}" for platform in missing_platforms)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate mergeable XCFramework metadata, binaries, and platform identity.")
    parser.add_argument("paths", nargs="+", help="XCFramework paths or directories containing XCFrameworks.")
    parser.add_argument(
        "--require-platform",
        action="append",
        default=[],
        help="Require an XCFramework platform key such as ios, ios-simulator, ios-maccatalyst, macos, tvos, watchos, or xros.",
    )
    arguments = parser.parse_args()

    results = [validate_xcframework(path, arguments.require_platform) for path in discover_xcframeworks(arguments.paths)]
    exit_code = 0 if all(not result["issues"] for result in results) else 1
    print(json.dumps({"xcframeworks": results}, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
