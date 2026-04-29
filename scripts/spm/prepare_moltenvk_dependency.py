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


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and stage the MoltenVK framework and headers dependencies.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--github-output", type=Path)
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


def main() -> int:
    arguments = _parse_arguments()
    output_dir = arguments.output_dir.resolve()
    zip_path = output_dir / f"MoltenVK-{packaging.MOLTENVK_PACKAGE.exact_version}.xcframework.zip"
    headers_zip_path = output_dir / f"MoltenVKHeaders-{packaging.MOLTENVK_PACKAGE.exact_version}.zip"
    extract_root = output_dir / "extracted"
    headers_extract_root = output_dir / "headers-extracted"

    try:
        _download_and_verify(
            packaging.MOLTENVK_ARTIFACT_URL,
            zip_path,
            packaging.MOLTENVK_ARTIFACT_CHECKSUM,
            "MoltenVK XCFramework",
        )
        _download_and_verify(
            packaging.MOLTENVK_HEADERS_ARTIFACT_URL,
            headers_zip_path,
            packaging.MOLTENVK_HEADERS_ARTIFACT_CHECKSUM,
            "MoltenVK headers",
        )

        _extract_archive(zip_path, extract_root)
        _extract_archive(headers_zip_path, headers_extract_root)
        xcframework_path = _find_moltenvk_xcframework(extract_root)
        headers_include_dir = _find_moltenvk_headers_include_dir(headers_extract_root)
        payload = {
            "zip_path": str(zip_path),
            "xcframework_path": str(xcframework_path),
            "headers_zip_path": str(headers_zip_path),
            "headers_include_dir": str(headers_include_dir),
            "version": packaging.MOLTENVK_PACKAGE.exact_version,
        }
        if arguments.github_output is not None:
            _write_github_output(arguments.github_output, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
