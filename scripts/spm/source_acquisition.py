#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_PATH = Path(__file__).resolve().with_name("source_acquisition.json")


def _load_contract(contract_path: Path) -> dict[str, str]:
    if not contract_path.exists():
        raise FileNotFoundError(f"source acquisition contract not found at {contract_path}")

    payload = json.loads(contract_path.read_text())
    required_keys = (
        "upstream_remote_name",
        "upstream_repository_url",
        "upstream_tag_ref_prefix",
    )
    for key in required_keys:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"source acquisition contract missing non-empty '{key}'")
    return payload


def _contract_for_repo(repo_root: Path, contract_override: Path | None) -> tuple[Path, dict[str, str]]:
    contract_path = contract_override or (repo_root / "scripts" / "spm" / "source_acquisition.json")
    return contract_path, _load_contract(contract_path)


def _run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repo-local upstream source acquisition helpers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch-tags", help="Fetch upstream tags into the dedicated local namespace.")
    fetch_parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    fetch_parser.add_argument("--contract", type=Path)

    export_parser = subparsers.add_parser("export-source", help="Export one upstream tag into a clean working tree.")
    export_parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    export_parser.add_argument("--contract", type=Path)
    export_parser.add_argument("--upstream-tag", required=True)
    export_parser.add_argument("--destination", type=Path, required=True)

    return parser.parse_args()


def _fetch_tags(repo_root: Path, contract_override: Path | None) -> None:
    _, contract = _contract_for_repo(repo_root, contract_override)
    remote_name = contract["upstream_remote_name"]
    upstream_url = contract["upstream_repository_url"]
    ref_prefix = contract["upstream_tag_ref_prefix"]

    try:
        subprocess.run(
            ["git", "remote", "get-url", remote_name],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        _run(["git", "remote", "add", remote_name, upstream_url], cwd=repo_root)

    _run(["git", "fetch", remote_name, f"refs/tags/*:{ref_prefix}/*"], cwd=repo_root)


def _export_source(repo_root: Path, contract_override: Path | None, upstream_tag: str, destination: Path) -> None:
    _, contract = _contract_for_repo(repo_root, contract_override)
    ref_prefix = contract["upstream_tag_ref_prefix"]
    ref_name = f"{ref_prefix}/{upstream_tag}"

    if destination.exists():
        shutil.rmtree(destination)

    _run(["git", "worktree", "add", "--detach", str(destination), ref_name], cwd=repo_root)
    _run(["git", "submodule", "update", "--init", "--recursive"], cwd=destination)


def main() -> int:
    arguments = _parse_arguments()
    try:
        if arguments.command == "fetch-tags":
            _fetch_tags(arguments.repo_root, arguments.contract)
        elif arguments.command == "export-source":
            _export_source(arguments.repo_root, arguments.contract, arguments.upstream_tag, arguments.destination)
        else:
            raise ValueError(f"unsupported command: {arguments.command}")
    except (FileNotFoundError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
