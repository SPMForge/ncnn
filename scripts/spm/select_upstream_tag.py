#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.spm import packaging
from scripts.spm import source_acquisition
from scripts.spm import tag_selection


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve an upstream tag for packaging release automation.")
    parser.add_argument("--explicit-tag", help="Use this upstream tag instead of selecting the latest one.")
    parser.add_argument(
        "--release-channel",
        choices=("sync", "alpha", "stable", "backfill"),
        default="sync",
        help="Release channel policy for mapping an upstream tag into a package tag.",
    )
    parser.add_argument(
        "--ref-prefix",
        help="Git ref prefix scanned when --explicit-tag is not provided. Defaults to the repo-local source acquisition contract.",
    )
    parser.add_argument("--repo-root", default=packaging.REPO_ROOT, type=Path)
    parser.add_argument(
        "--github-output",
        type=Path,
        help="Optional GitHub Actions output file. When provided, upstream_tag/package_tag are appended.",
    )
    return parser.parse_args()


def _list_refs(repo_root: Path, ref_prefix: str) -> list[str]:
    command = [
        "git",
        "for-each-ref",
        "--format=%(refname)",
        ref_prefix,
    ]
    process = subprocess.run(
        command,
        check=True,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in process.stdout.splitlines() if line.strip()]


def _rev_parse(repo_root: Path, ref_name: str) -> str:
    process = subprocess.run(
        ["git", "rev-parse", f"{ref_name}^{{commit}}"],
        check=True,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip()


def _resolve_upstream_tag(arguments: argparse.Namespace) -> str:
    if arguments.explicit_tag:
        packaging.package_tag_for_upstream_tag(arguments.explicit_tag)
        return arguments.explicit_tag

    ref_prefix = arguments.ref_prefix
    if not ref_prefix:
        contract_path = arguments.repo_root / "scripts" / "spm" / "source_acquisition.json"
        if contract_path.exists():
            _, contract = source_acquisition._contract_for_repo(arguments.repo_root, None)
            ref_prefix = contract["upstream_tag_ref_prefix"]
        else:
            ref_prefix = "refs/upstream-tags"

    refs = _list_refs(arguments.repo_root, ref_prefix)
    return tag_selection.select_latest_stable_tag(refs)


def _resolve_package_tag(arguments: argparse.Namespace, upstream_tag: str) -> str:
    if arguments.release_channel == "stable":
        return packaging.stable_package_tag_for_upstream_tag(upstream_tag)

    package_refs = _list_refs(arguments.repo_root, "refs/tags")
    if arguments.release_channel == "sync":
        latest_alpha_tag = packaging.latest_alpha_package_tag_for_upstream_tag(upstream_tag, package_refs)
        if latest_alpha_tag is None:
            return packaging.package_tag_for_upstream_tag(upstream_tag)

        head_commit = _rev_parse(arguments.repo_root, "HEAD")
        latest_alpha_commit = _rev_parse(arguments.repo_root, f"refs/tags/{latest_alpha_tag}")
        if latest_alpha_commit == head_commit:
            return latest_alpha_tag

        alpha_number = packaging.next_alpha_number_for_upstream_tag(upstream_tag, package_refs)
        return packaging.package_tag_for_upstream_tag(upstream_tag, alpha_number=alpha_number)

    if arguments.release_channel not in {"alpha", "backfill"}:
        return packaging.package_tag_for_upstream_tag(upstream_tag)

    alpha_number = packaging.next_alpha_number_for_upstream_tag(upstream_tag, package_refs)
    return packaging.package_tag_for_upstream_tag(upstream_tag, alpha_number=alpha_number)


def main() -> int:
    arguments = _parse_arguments()
    upstream_tag = _resolve_upstream_tag(arguments)
    package_tag = _resolve_package_tag(arguments, upstream_tag)

    if arguments.github_output is not None:
        with arguments.github_output.open("a") as output_file:
            output_file.write(f"upstream_tag={upstream_tag}\n")
            output_file.write(f"package_tag={package_tag}\n")

    print(json.dumps({"upstream_tag": upstream_tag, "package_tag": package_tag}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
