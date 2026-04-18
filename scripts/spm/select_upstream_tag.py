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
from scripts.spm import tag_selection


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve an upstream tag for packaging release automation.")
    parser.add_argument("--explicit-tag", help="Use this upstream tag instead of selecting the latest one.")
    parser.add_argument(
        "--ref-prefix",
        default="refs/upstream-tags",
        help="Git ref prefix scanned when --explicit-tag is not provided.",
    )
    parser.add_argument("--repo-root", default=packaging.REPO_ROOT, type=Path)
    parser.add_argument(
        "--github-output",
        type=Path,
        help="Optional GitHub Actions output file. When provided, upstream_tag/package_tag are appended.",
    )
    return parser.parse_args()


def _resolve_upstream_tag(arguments: argparse.Namespace) -> str:
    if arguments.explicit_tag:
        packaging.package_tag_for_upstream_tag(arguments.explicit_tag)
        return arguments.explicit_tag

    command = [
        "git",
        "for-each-ref",
        "--format=%(refname)",
        arguments.ref_prefix,
    ]
    process = subprocess.run(
        command,
        check=True,
        cwd=arguments.repo_root,
        capture_output=True,
        text=True,
    )
    refs = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    return tag_selection.select_latest_stable_tag(refs)


def main() -> int:
    arguments = _parse_arguments()
    upstream_tag = _resolve_upstream_tag(arguments)
    package_tag = packaging.package_tag_for_upstream_tag(upstream_tag)

    if arguments.github_output is not None:
        with arguments.github_output.open("a") as output_file:
            output_file.write(f"upstream_tag={upstream_tag}\n")
            output_file.write(f"package_tag={package_tag}\n")

    print(json.dumps({"upstream_tag": upstream_tag, "package_tag": package_tag}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
