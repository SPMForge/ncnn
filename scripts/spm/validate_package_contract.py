#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.spm import packaging


REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the generated Package.swift contract from freshly built release metadata."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--release-metadata",
        action="append",
        dest="release_metadata_paths",
        required=True,
        type=Path,
        help="Path to a variant release metadata json file. Pass once per artifact.",
    )
    parser.add_argument("--package-name", default=packaging.DEFAULT_PACKAGE_NAME)
    parser.add_argument("--owner", default=packaging.DEFAULT_OWNER)
    parser.add_argument("--repo", default=packaging.DEFAULT_REPO)
    return parser.parse_args()


def _run(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _capture_output(command: list[str], cwd: Path | None = None) -> str:
    process = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    return process.stdout


def _stage_validation_root(package_root: Path) -> None:
    package_root.mkdir(parents=True, exist_ok=True)


def _render_release_metadata(
    package_root: Path,
    release_metadata_paths: list[Path],
    package_name: str,
    owner: str,
    repo: str,
) -> Path:
    current_release_json = package_root / "scripts" / "spm" / "current_release.json"
    command = [
        sys.executable,
        str(packaging.SCRIPTS_ROOT / "render_package.py"),
        "--output",
        str(package_root / "Package.swift"),
        "--package-name",
        package_name,
        "--owner",
        owner,
        "--repo",
        repo,
        "--current-release-json",
        str(current_release_json),
    ]
    for metadata_path in release_metadata_paths:
        command.extend(["--release-metadata", str(metadata_path)])
    _run(command, cwd=REPO_ROOT)
    return current_release_json


def _validate_manifest(package_root: Path) -> None:
    _capture_output(["swift", "package", "dump-package"], cwd=package_root)


def main() -> int:
    arguments = _parse_arguments()
    release_metadata_paths = [path.resolve() for path in arguments.release_metadata_paths]
    repo_root = arguments.repo_root.resolve()

    try:
        with tempfile.TemporaryDirectory(prefix="ncnn-package-contract-") as temporary_directory:
            package_root = Path(temporary_directory)
            _stage_validation_root(package_root)
            current_release_json = _render_release_metadata(
                package_root=package_root,
                release_metadata_paths=release_metadata_paths,
                package_name=arguments.package_name,
                owner=arguments.owner,
                repo=arguments.repo,
            )
            _validate_manifest(package_root)
            print(
                json.dumps(
                    {
                        "package_root": str(package_root),
                        "current_release_json": str(current_release_json),
                        "release_count": len(release_metadata_paths),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
