#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.spm import packaging


def required_release_asset_names(upstream_tag: str) -> tuple[str, ...]:
    return tuple(packaging.asset_name_for_variant(variant, upstream_tag) for variant in packaging.VARIANTS)


def _load_release_view(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("release view payload must be a JSON object")
    return payload


def inspect_release_state(
    *,
    package_tag: str,
    upstream_tag: str,
    release_channel: str,
    tag_exists: bool,
    release_view: dict[str, object] | None,
    latest_release_tag: str | None,
) -> dict[str, object]:
    if release_channel not in {"sync", "alpha", "stable"}:
        raise ValueError(f"unsupported release channel: {release_channel}")

    expected_prerelease = release_channel != "stable"
    required_assets = required_release_asset_names(upstream_tag)
    published_assets: tuple[str, ...] = ()
    release_exists = release_view is not None
    release_is_prerelease = False
    release_is_latest = latest_release_tag == package_tag if latest_release_tag else False

    if release_view is not None:
        raw_prerelease = release_view.get("isPrerelease")
        if not isinstance(raw_prerelease, bool):
            raise ValueError("release view payload missing boolean isPrerelease")
        release_is_prerelease = raw_prerelease

        raw_assets = release_view.get("assets")
        if not isinstance(raw_assets, list):
            raise ValueError("release view payload missing assets list")
        asset_names: list[str] = []
        for asset in raw_assets:
            if not isinstance(asset, dict):
                raise ValueError("release asset payload must be an object")
            name = asset.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError("release asset payload missing non-empty name")
            asset_names.append(name)
        published_assets = tuple(sorted(asset_names))

    missing_assets = tuple(asset for asset in required_assets if asset not in published_assets)
    metadata_needs_repair = False
    if release_exists:
        if expected_prerelease:
            metadata_needs_repair = (not release_is_prerelease) or release_is_latest
        else:
            metadata_needs_repair = release_is_prerelease

    if not tag_exists:
        mode = "create"
    elif (not release_exists) or missing_assets or metadata_needs_repair:
        mode = "repair"
    else:
        mode = "skip"

    return {
        "package_tag": package_tag,
        "upstream_tag": upstream_tag,
        "release_channel": release_channel,
        "tag_exists": tag_exists,
        "release_exists": release_exists,
        "required_assets": list(required_assets),
        "published_assets": list(published_assets),
        "missing_assets": list(missing_assets),
        "expected_prerelease": expected_prerelease,
        "release_is_prerelease": release_is_prerelease,
        "release_is_latest": release_is_latest,
        "metadata_needs_repair": metadata_needs_repair,
        "mode": mode,
    }


def _write_github_output(path: Path, payload: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"mode={payload['mode']}\n")
        handle.write(f"release_exists={str(payload['release_exists']).lower()}\n")
        handle.write(f"metadata_needs_repair={str(payload['metadata_needs_repair']).lower()}\n")
        handle.write(f"missing_assets={','.join(payload['missing_assets'])}\n")


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect GitHub release completeness and metadata drift.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect-release", help="Inspect whether a package tag should be created, repaired, or skipped.")
    inspect_parser.add_argument("--package-tag", required=True)
    inspect_parser.add_argument("--upstream-tag", required=True)
    inspect_parser.add_argument("--release-channel", required=True)
    inspect_parser.add_argument("--tag-exists", action="store_true")
    inspect_parser.add_argument("--release-view-json", type=Path)
    inspect_parser.add_argument("--latest-release-tag")
    inspect_parser.add_argument("--github-output", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = _parse_arguments()

    try:
        if arguments.command != "inspect-release":
            raise ValueError(f"unsupported command: {arguments.command}")
        payload = inspect_release_state(
            package_tag=arguments.package_tag,
            upstream_tag=arguments.upstream_tag,
            release_channel=arguments.release_channel,
            tag_exists=arguments.tag_exists,
            release_view=_load_release_view(arguments.release_view_json),
            latest_release_tag=arguments.latest_release_tag,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1

    if arguments.github_output is not None:
        _write_github_output(arguments.github_output, payload)

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
