#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.spm import packaging

DEFAULT_OUTPUT_DIR = packaging.REPO_ROOT / "build" / "spm" / "moltenvk"


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and stage the MoltenVK framework and headers dependencies.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for staged MoltenVK artifacts. Defaults to {DEFAULT_OUTPUT_DIR}.",
    )
    parser.add_argument("--github-output", type=Path)
    version_group = parser.add_mutually_exclusive_group()
    version_group.add_argument(
        "--version",
        help=(
            "MoltenVK release tag to stage. Defaults to scripts/spm/packaging.py, or "
            f"${packaging.MOLTENVK_VERSION_ENV} when set."
        ),
    )
    version_group.add_argument(
        "--latest",
        action="store_true",
        help="Resolve the latest MoltenVK GitHub release that exposes the required framework and headers assets.",
    )
    parser.add_argument(
        "--xcframework-checksum",
        help=(
            "Expected SHA-256 for MoltenVK-<version>.xcframework.zip. "
            "Defaults to the pinned package checksum, the matching environment override, "
            "or the GitHub release asset digest."
        ),
    )
    parser.add_argument(
        "--headers-checksum",
        help=(
            "Expected SHA-256 for MoltenVKHeaders-<version>.zip. "
            "Defaults to the pinned package checksum, the matching environment override, "
            "or the GitHub release asset digest."
        ),
    )
    parser.add_argument(
        "--write-pin",
        nargs="?",
        const=packaging.MOLTENVK_DEPENDENCY_CONFIG_PATH,
        type=Path,
        help=(
            "Write a repo-local moltenvk_dependency.json pin using the resolved version and checksums. "
            "Defaults to scripts/spm/moltenvk_dependency.json when no path is provided."
        ),
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, output_path.open("wb") as output_file:
        shutil.copyfileobj(response, output_file)


def _github_json(url: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "SPMForge-ncnn-moltenvk-dependency-prep",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def _release_asset_checksum(version: str, asset_name: str) -> str:
    release_url = f"https://api.github.com/repos/SPMForge/MoltenVK/releases/tags/{version}"
    payload = _github_json(release_url)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid MoltenVK release payload for {version}")
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise ValueError(f"MoltenVK release {version} does not expose assets")
    for asset in assets:
        if not isinstance(asset, dict) or asset.get("name") != asset_name:
            continue
        digest = asset.get("digest")
        if isinstance(digest, str) and digest.startswith("sha256:"):
            return digest.removeprefix("sha256:")
    raise ValueError(f"MoltenVK release {version} does not expose a SHA-256 digest for {asset_name}")


def _has_release_assets(release: dict[str, object], tag_name: str) -> bool:
    assets = release.get("assets")
    if not isinstance(assets, list):
        return False
    asset_names = {asset.get("name") for asset in assets if isinstance(asset, dict)}
    return {
        f"MoltenVK-{tag_name}.xcframework.zip",
        f"MoltenVKHeaders-{tag_name}.zip",
    }.issubset(asset_names)


def _latest_moltenvk_release_tag() -> str:
    releases_url = "https://api.github.com/repos/SPMForge/MoltenVK/releases?per_page=30"
    payload = _github_json(releases_url)
    if not isinstance(payload, list):
        raise ValueError("invalid MoltenVK releases payload")
    for release in payload:
        if not isinstance(release, dict):
            continue
        tag_name = release.get("tag_name")
        if isinstance(tag_name, str) and tag_name and _has_release_assets(release, tag_name):
            return tag_name
    raise ValueError("no MoltenVK release exposes the required framework and headers assets")


def _resolve_checksum(explicit_checksum: str | None, configured_checksum: str, version: str, asset_name: str) -> str:
    if explicit_checksum:
        return explicit_checksum
    if configured_checksum:
        return configured_checksum
    return _release_asset_checksum(version, asset_name)


def _download_and_verify(url: str, output_path: Path, expected_checksum: str, label: str) -> None:
    if not output_path.is_file() or _sha256(output_path) != expected_checksum:
        _download(url, output_path)
    actual_checksum = _sha256(output_path)
    if actual_checksum != expected_checksum:
        raise ValueError(f"{label} checksum mismatch: expected {expected_checksum}, found {actual_checksum}")


def _extract_archive(zip_path: Path, destination_dir: Path) -> None:
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    destination_dir.mkdir(parents=True)

    ditto_path = shutil.which("ditto")
    if ditto_path and Path(ditto_path).exists():
        subprocess.run([ditto_path, "-x", "-k", str(zip_path), str(destination_dir)], check=True)
        return

    unzip_path = shutil.which("unzip")
    if unzip_path and Path(unzip_path).exists():
        subprocess.run([unzip_path, "-q", str(zip_path), "-d", str(destination_dir)], check=True)
        return

    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(destination_dir)


def _find_moltenvk_xcframework(root: Path) -> Path:
    matches = sorted(path for path in root.rglob("MoltenVK.xcframework") if path.is_dir())
    if len(matches) != 1:
        raise ValueError(f"expected one MoltenVK.xcframework under {root}, found {len(matches)}")
    return matches[0]


def _find_moltenvk_headers_include_dir(root: Path) -> Path:
    matches = sorted(
        path
        for path in root.rglob("include")
        if (path / "vulkan" / "vulkan.h").is_file()
        and (path / "MoltenVK" / "vulkan" / "vk_platform.h").is_file()
    )
    if len(matches) != 1:
        raise ValueError(f"expected one MoltenVK headers include directory under {root}, found {len(matches)}")
    return matches[0]


def _write_github_output(path: Path, values: dict[str, str]) -> None:
    with path.open("a") as output_file:
        for key, value in values.items():
            output_file.write(f"{key}={value}\n")


def _write_dependency_pin(path: Path, version: str) -> None:
    payload = {
        "package_name": packaging.MOLTENVK_PACKAGE.package_name,
        "url": packaging.MOLTENVK_PACKAGE.url,
        "version": version,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    arguments = _parse_arguments()
    output_dir = arguments.output_dir.resolve()

    try:
        if arguments.latest:
            version = _latest_moltenvk_release_tag()
        else:
            version = (arguments.version or packaging.MOLTENVK_PACKAGE.exact_version).strip()
        zip_asset_name = f"MoltenVK-{version}.xcframework.zip"
        headers_zip_asset_name = f"MoltenVKHeaders-{version}.zip"
        zip_path = output_dir / zip_asset_name
        headers_zip_path = output_dir / headers_zip_asset_name
        extract_root = output_dir / "extracted"
        headers_extract_root = output_dir / "headers-extracted"
        artifact_url = f"https://github.com/SPMForge/MoltenVK/releases/download/{version}/{zip_asset_name}"
        headers_artifact_url = f"https://github.com/SPMForge/MoltenVK/releases/download/{version}/{headers_zip_asset_name}"
        artifact_checksum = _resolve_checksum(
            arguments.xcframework_checksum,
            packaging.MOLTENVK_ARTIFACT_CHECKSUM if version == packaging.MOLTENVK_PACKAGE.exact_version else "",
            version,
            zip_asset_name,
        )
        headers_artifact_checksum = _resolve_checksum(
            arguments.headers_checksum,
            packaging.MOLTENVK_HEADERS_ARTIFACT_CHECKSUM if version == packaging.MOLTENVK_PACKAGE.exact_version else "",
            version,
            headers_zip_asset_name,
        )
        _download_and_verify(
            artifact_url,
            zip_path,
            artifact_checksum,
            "MoltenVK XCFramework",
        )
        _download_and_verify(
            headers_artifact_url,
            headers_zip_path,
            headers_artifact_checksum,
            "MoltenVK headers",
        )

        _extract_archive(zip_path, extract_root)
        _extract_archive(headers_zip_path, headers_extract_root)
        xcframework_path = _find_moltenvk_xcframework(extract_root)
        headers_include_dir = _find_moltenvk_headers_include_dir(headers_extract_root)
        payload = {
            "headers_checksum": headers_artifact_checksum,
            "headers_zip_path": str(headers_zip_path),
            "headers_include_dir": str(headers_include_dir),
            "version": version,
            "xcframework_checksum": artifact_checksum,
            "xcframework_path": str(xcframework_path),
            "zip_path": str(zip_path),
        }
        if arguments.github_output is not None:
            _write_github_output(arguments.github_output, payload)
        if arguments.write_pin is not None:
            _write_dependency_pin(
                arguments.write_pin,
                version,
            )
        print(json.dumps(payload, indent=2, sort_keys=True))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
