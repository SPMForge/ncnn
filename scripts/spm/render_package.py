#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.spm import packaging


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Package.swift from release metadata.")
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
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path for a fully rendered static Package.swift.",
    )
    parser.add_argument(
        "--current-release-json",
        default=packaging.CURRENT_RELEASE_METADATA_PATH,
        type=Path,
        help="Write the merged release metadata to this path.",
    )
    return parser.parse_args()


def _load_release_asset(path: Path) -> packaging.ReleaseAsset:
    payload = json.loads(path.read_text())
    variant = packaging.variant_for_target_name(payload["target_name"])
    return packaging.ReleaseAsset(
        variant=variant,
        upstream_tag=payload["upstream_tag"],
        package_tag=payload["package_tag"],
        checksum=payload["checksum"],
    )


def _sort_release_assets(releases: list[packaging.ReleaseAsset]) -> list[packaging.ReleaseAsset]:
    variant_order = {variant.target_name: index for index, variant in enumerate(packaging.VARIANTS)}
    return sorted(releases, key=lambda release: variant_order[release.variant.target_name])


def _write_combined_metadata(
    output_path: Path,
    package_name: str,
    owner: str,
    repo: str,
    releases: list[packaging.ReleaseAsset],
) -> None:
    payload = {
        "package_name": package_name,
        "owner": owner,
        "repo": repo,
        "releases": [
            {
                "target_name": release.variant.target_name,
                "product_name": release.variant.product_name,
                "module_name": release.variant.module_name,
                "upstream_tag": release.upstream_tag,
                "package_tag": release.package_tag,
                "asset_name": packaging.asset_name_for_variant(release.variant, release.upstream_tag),
                "url": packaging.release_url(owner, repo, release.package_tag, release.variant, release.upstream_tag),
                "checksum": release.checksum,
                "platforms": [platform.swiftpm_platform for platform in release.variant.platforms],
            }
            for release in releases
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    arguments = _parse_arguments()
    releases = _sort_release_assets([_load_release_asset(path) for path in arguments.release_metadata_paths])

    package_contents = packaging.render_package_swift(
        package_name=arguments.package_name,
        owner=arguments.owner,
        repo=arguments.repo,
        releases=releases,
    )

    if arguments.output is not None:
        arguments.output.write_text(package_contents)
    _write_combined_metadata(
        arguments.current_release_json,
        arguments.package_name,
        arguments.owner,
        arguments.repo,
        releases,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
