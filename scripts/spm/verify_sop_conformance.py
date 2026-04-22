#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read_text(path: Path) -> str:
    require(path.exists(), f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def main() -> int:
    workflow_names = sorted(path.name for path in WORKFLOWS_DIR.glob("*.yml"))
    require(
        workflow_names
        == [
            "_publish-upstream-release-core.yml",
            "publish-latest-upstream-alpha.yml",
            "publish-upstream-release-manually.yml",
            "validate-apple-release-pipeline.yml",
        ],
        f"unexpected workflow set: {workflow_names}",
    )

    readme = read_text(REPO_ROOT / "README.md")
    core_workflow = read_text(WORKFLOWS_DIR / "_publish-upstream-release-core.yml")
    validate_workflow = read_text(WORKFLOWS_DIR / "validate-apple-release-pipeline.yml")
    package_swift = read_text(REPO_ROOT / "Package.swift")

    require("wrapper repository" in readme, "README must describe the repo as a wrapper repository")
    require("refs/upstream-tags/*" in readme, "README must document refs/upstream-tags/*")
    require("workflow_call:" in core_workflow, "publish core must be reusable via workflow_call")
    require("--latest=false" in core_workflow, "alpha publishes must force latest=false")
    require("gh release upload" in core_workflow, "publish core must support repair uploads")
    require("gh api --method PATCH" in core_workflow, "publish core must normalize release metadata")
    require("DEVELOPER_DIR:" not in core_workflow, "publish core must not hardcode DEVELOPER_DIR")
    require("push:" in validate_workflow and "pull_request:" in validate_workflow, "validation workflow must run on push and pull_request")
    require("DEVELOPER_DIR:" not in validate_workflow, "validation workflow must not hardcode DEVELOPER_DIR")
    require('path: "Artifacts/' not in package_swift, "committed Package.swift must not use repo-local artifact paths")
    require("FileManager.default.fileExists" not in package_swift, "committed Package.swift must not switch on local checkout state")

    source_acquisition = json.loads(read_text(REPO_ROOT / "scripts" / "spm" / "source_acquisition.json"))
    require(
        source_acquisition.get("upstream_tag_ref_prefix") == "refs/upstream-tags",
        "source acquisition contract must fetch into refs/upstream-tags",
    )
    require((REPO_ROOT / "scripts" / "spm" / "platforms.json").exists(), "platform metadata must exist")
    require((REPO_ROOT / "scripts" / "spm" / "current_release.json").exists(), "release metadata must exist")

    print("ncnn SOP conformance verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
