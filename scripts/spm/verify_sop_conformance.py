#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
PRODUCTION_SCRIPT_PATHS = tuple(sorted((REPO_ROOT / "scripts" / "spm").glob("*.py")))
PRODUCTION_WORKFLOW_PATHS = (
    REPO_ROOT / ".github" / "workflows" / "_publish-upstream-release-core.yml",
    REPO_ROOT / ".github" / "workflows" / "validate-apple-release-pipeline.yml",
)
_DEPLOYMENT_TARGET_CONTEXT_PATTERN = re.compile(
    r"(deployment_target|Platform\(|\.iOS\(|\.macOS\(|\.macCatalyst\(|\.tvOS\(|\.watchOS\(|\.visionOS\()",
    re.IGNORECASE,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read_text(path: Path) -> str:
    require(path.exists(), f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def _load_platform_deployment_targets(repo_root: Path) -> dict[str, str]:
    payload = json.loads(read_text(repo_root / "scripts" / "spm" / "platforms.json"))
    package_platforms = payload.get("package_platforms")
    require(
        isinstance(package_platforms, dict),
        f"invalid platform metadata in {repo_root / 'scripts' / 'spm' / 'platforms.json'}",
    )
    return {str(key): str(value) for key, value in package_platforms.items()}


def _load_moltenvk_minimum_platforms(repo_root: Path) -> dict[str, str]:
    payload = json.loads(read_text(repo_root / "scripts" / "spm" / "moltenvk_dependency.json"))
    minimum_platforms = payload.get("minimum_platforms")
    require(
        isinstance(minimum_platforms, dict),
        "MoltenVK dependency pin must record provider minimum platforms",
    )
    return {str(key): str(value) for key, value in minimum_platforms.items()}


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(component) for component in version.split("."))


def _assert_package_platforms_cover_moltenvk_provider_floor(repo_root: Path) -> None:
    package_platforms = _load_platform_deployment_targets(repo_root)
    moltenvk_minimum_platforms = _load_moltenvk_minimum_platforms(repo_root)
    for platform_key, provider_floor in moltenvk_minimum_platforms.items():
        package_floor = package_platforms.get(platform_key)
        require(
            package_floor is not None,
            f"package platforms must include MoltenVK provider platform {platform_key}",
        )
        require(
            _version_tuple(package_floor) >= _version_tuple(provider_floor),
            f"package {platform_key} deployment target {package_floor} must be no lower than "
            f"MoltenVK provider floor {provider_floor}",
        )


def _assert_no_hardcoded_deployment_targets(repo_root: Path, file_paths: tuple[Path, ...]) -> None:
    deployment_targets = sorted(set(_load_platform_deployment_targets(repo_root).values()))
    for path in file_paths:
        contents = read_text(path)
        for deployment_target in deployment_targets:
            literal_pattern = re.compile(rf"(?<![0-9A-Za-z]){re.escape(deployment_target)}(?![0-9A-Za-z])")
            for line in contents.splitlines():
                if not literal_pattern.search(line):
                    continue
                require(
                    _DEPLOYMENT_TARGET_CONTEXT_PATTERN.search(line) is None,
                    "deployment target "
                    f"{deployment_target} must stay centralized in scripts/spm/platforms.json; "
                    f"found hardcoded value in {path}",
                )


def main(repo_root: Path = REPO_ROOT) -> int:
    workflows_dir = repo_root / ".github" / "workflows"
    workflow_names = sorted(path.name for path in workflows_dir.glob("*.yml"))
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

    readme = read_text(repo_root / "README.md")
    core_workflow = read_text(workflows_dir / "_publish-upstream-release-core.yml")
    sync_workflow = read_text(workflows_dir / "publish-latest-upstream-alpha.yml")
    manual_workflow = read_text(workflows_dir / "publish-upstream-release-manually.yml")
    validate_workflow = read_text(workflows_dir / "validate-apple-release-pipeline.yml")
    release_document = read_text(repo_root / "docs" / "how-to-build" / "swiftpm-binary-package.md")
    packaging_script = read_text(repo_root / "scripts" / "spm" / "packaging.py")
    build_script = read_text(repo_root / "scripts" / "spm" / "build_apple_xcframework.py")
    prepare_moltenvk_script = read_text(repo_root / "scripts" / "spm" / "prepare_moltenvk_dependency.py")
    validate_package_contract_script = read_text(repo_root / "scripts" / "spm" / "validate_package_contract.py")
    moltenvk_dependency_config = read_text(repo_root / "scripts" / "spm" / "moltenvk_dependency.json")
    package_swift = read_text(repo_root / "Package.swift")

    require("wrapper repository" in readme, "README must describe the repo as a wrapper repository")
    require("refs/upstream-tags/*" in readme, "README must document refs/upstream-tags/*")
    require(
        "Alpha package tags point directly at immutable generated metadata commits" in readme,
        "README must document tag-only alpha release metadata commits",
    )
    require("Stable promotions may update the default branch" in readme, "README must document stable default-branch updates")
    require("workflow_call:" in core_workflow, "publish core must be reusable via workflow_call")
    require("publish_to_default_branch:" in core_workflow, "publish core must make default-branch updates explicit")
    require(
        "publish_to_default_branch is only supported for stable releases." in core_workflow,
        "publish core must fail loudly when non-stable channels request default-branch writes",
    )
    require(
        "publish_to_default_branch: false" in sync_workflow,
        "auto alpha workflow must not write the default branch",
    )
    require(
        "publish_to_default_branch:" in manual_workflow
        and "type: boolean" in manual_workflow
        and "default: false" in manual_workflow
        and "inputs.release_channel == 'stable' && inputs.publish_to_default_branch" in manual_workflow,
        "manual workflow must expose an explicit stable-only default-branch publish choice",
    )
    require("--latest=false" in core_workflow, "alpha publishes must force latest=false")
    require("gh release upload" in core_workflow, "publish core must support repair uploads")
    require("gh api --method PATCH" in core_workflow, "publish core must normalize release metadata")
    require("select-publication-tag" in core_workflow, "publish core must resolve final alpha tags from rendered manifests")
    require("git switch --detach" in core_workflow, "publish core must create generated metadata commits off the default branch")
    require(
        'git push origin "refs/tags/${{ steps.publication_plan.outputs.final_package_tag }}"' in core_workflow,
        "publish core must publish package tags for generated metadata commits",
    )
    require(
        'HEAD:refs/heads/' not in core_workflow and "release/<package_tag>" not in core_workflow,
        "publish core must not publish release/<package_tag> branches as part of the alpha release contract",
    )
    require("actions/cache/restore@v5" in core_workflow, "publish core must use restore-only cache action for ccache")
    require("actions/cache/save@v5" in core_workflow, "publish core must use save-only cache action for ccache")
    require(
        "steps.restore_ccache.outcome == 'success'" in core_workflow
        and "steps.build_xcframework.outcome == 'success'" in core_workflow
        and "steps.verify_ccache_payload.outcome == 'success'" in core_workflow,
        "publish core must save ccache only after restore, build, and payload verification succeed",
    )
    require(
        "steps.restore_ccache.outputs.cache-hit != 'true'" in core_workflow
        and "steps.restore_ccache.outputs.cache-primary-key" in core_workflow,
        "publish core must save ccache only for misses or stale restores using the restored primary key",
    )
    require(
        "compiler cache remained empty after build-xcframework" in core_workflow,
        "publish core must fail loudly when build-xcframework leaves ccache empty",
    )
    require("overwrite: true" in core_workflow, "publish core artifact uploads must overwrite on rerun")
    require(
        "--release-archive artifacts/ncnn/ncnn-*.xcframework.zip" in core_workflow
        and "--release-archive artifacts/ncnn_vulkan/ncnn-*.xcframework.zip" in core_workflow,
        "publish core must validate package contract against fresh release archives",
    )
    require(
        "--require-strong-dependency @rpath/MoltenVK.framework/MoltenVK" in core_workflow
        and "--forbid-dependency @rpath/libvulkan.dylib" in core_workflow
        and "--forbid-dependency @rpath/libvulkan.1.dylib" in core_workflow,
        "publish core must validate the NCNNVulkan strong MoltenVK dependency and reject retired Vulkan loaders",
    )
    require(
        "--moltenvk-xcframework" in core_workflow
        and "--moltenvk-include-dir" in core_workflow
        and "headers_include_dir" in core_workflow,
        "publish core must pass both MoltenVK framework and provider-owned headers inputs to Vulkan builds",
    )
    require("hashFiles(" in core_workflow, "publish core must partition ccache by build-script inputs")
    require("DEVELOPER_DIR:" not in core_workflow, "publish core must not hardcode DEVELOPER_DIR")
    require(
        "push:" in validate_workflow and "pull_request:" in validate_workflow,
        "validation workflow must run on push and pull_request",
    )
    require(
        "moltenvk_version:" in validate_workflow
        and "SPMFORGE_MOLTENVK_VERSION: ${{ inputs.moltenvk_version }}" in validate_workflow
        and 'moltenvk_args+=(--version "$SPMFORGE_MOLTENVK_VERSION")' in validate_workflow,
        "validation workflow must expose and pass a manual MoltenVK development-version override",
    )
    require(
        "moltenvk_version:" not in core_workflow
        and "SPMFORGE_MOLTENVK_VERSION" not in core_workflow
        and "SPMFORGE_MOLTENVK_VERSION" not in sync_workflow
        and "SPMFORGE_MOLTENVK_VERSION" not in manual_workflow,
        "publish workflows must not expose MoltenVK development-version overrides",
    )
    require("actions/cache/restore@v5" in validate_workflow, "validation workflow must use restore-only cache action for ccache")
    require("actions/cache/save@v5" in validate_workflow, "validation workflow must use save-only cache action for ccache")
    require(
        "steps.restore_ccache.outcome == 'success'" in validate_workflow
        and "steps.build_xcframework.outcome == 'success'" in validate_workflow
        and "steps.verify_ccache_payload.outcome == 'success'" in validate_workflow,
        "validation workflow must save ccache only after restore, build, and payload verification succeed",
    )
    require(
        "steps.restore_ccache.outputs.cache-hit != 'true'" in validate_workflow
        and "steps.restore_ccache.outputs.cache-primary-key" in validate_workflow,
        "validation workflow must save ccache only for misses or stale restores using the restored primary key",
    )
    require(
        "compiler cache remained empty after build-xcframework" in validate_workflow,
        "validation workflow must fail loudly when build-xcframework leaves ccache empty",
    )
    require("actions/upload-artifact@v7" in validate_workflow, "validation workflow must use Node24-ready upload action")
    require("overwrite: true" in validate_workflow, "validation artifact uploads must overwrite on rerun")
    require(
        "--release-archive artifacts/ncnn/ncnn-*.xcframework.zip" in validate_workflow
        and "--release-archive artifacts/ncnn_vulkan/ncnn-*.xcframework.zip" in validate_workflow,
        "validation workflow must validate package contract against fresh release archives",
    )
    require(
        "--require-strong-dependency @rpath/MoltenVK.framework/MoltenVK" in validate_workflow
        and "--forbid-dependency @rpath/libvulkan.dylib" in validate_workflow
        and "--forbid-dependency @rpath/libvulkan.1.dylib" in validate_workflow,
        "validation workflow must validate the NCNNVulkan strong MoltenVK dependency and reject retired Vulkan loaders",
    )
    require(
        "--moltenvk-xcframework" in validate_workflow
        and "--moltenvk-include-dir" in validate_workflow
        and "headers_include_dir" in validate_workflow,
        "validation workflow must pass both MoltenVK framework and provider-owned headers inputs to Vulkan builds",
    )
    require("hashFiles(" in validate_workflow, "validation workflow must partition ccache by build-script inputs")
    require("DEVELOPER_DIR:" not in validate_workflow, "validation workflow must not hardcode DEVELOPER_DIR")
    require(
        "runtime_dependency_model" in packaging_script
        and "strong_runtime_dependencies" in packaging_script
        and "forbidden_runtime_dependencies" in packaging_script,
        "packaging contract must record runtime dependency model, strong runtime dependencies, and forbidden runtime dependencies",
    )
    require(
        "MOLTENVK_HEADERS_ARTIFACT_URL" in packaging_script
        and "MOLTENVK_HEADERS_ARTIFACT_CHECKSUM" in packaging_script,
        "packaging contract must pin the provider-owned MoltenVKHeaders artifact",
    )
    require(
        "moltenvk_dependency.json" in packaging_script
        and '"version"' in moltenvk_dependency_config
        and "optional_fields" in packaging_script,
        "MoltenVK publish dependency pin must live in scripts/spm/moltenvk_dependency.json and allow omitted checksums",
    )
    require(
        "SPMFORGE_MOLTENVK_VERSION" in packaging_script
        and "--version" in prepare_moltenvk_script
        and "--latest" in prepare_moltenvk_script
        and "--write-pin" in prepare_moltenvk_script
        and "DEFAULT_OUTPUT_DIR" in prepare_moltenvk_script
        and "Authorization" in prepare_moltenvk_script
        and "_release_asset_checksum" in prepare_moltenvk_script,
        "MoltenVK dependency preparation must allow explicit development-version overrides without editing the release contract",
    )
    require(
        "GITHUB_TOKEN: ${{ github.token }}" in core_workflow
        and "GITHUB_TOKEN: ${{ github.token }}" in validate_workflow,
        "MoltenVK digest resolution must use the GitHub Actions token instead of anonymous release API requests",
    )
    require(
        "prepare_moltenvk_dependency.py --latest --write-pin" in readme,
        "README must document the one-command MoltenVK pin promotion path",
    )
    require(
        "_moltenvk_include_dir_for_platform" not in build_script
        and "MoltenVKHeaders include directory" in build_script,
        "Vulkan builds must consume the provider-owned MoltenVKHeaders include directory instead of generating a local overlay",
    )
    require(
        "MoltenVK/vulkan/" in build_script and "vulkan/" in build_script,
        "Vulkan public headers must rewrite SDK-style Vulkan includes to MoltenVK framework-style includes",
    )
    require(
        "/gpu.h" in validate_package_contract_script and "get_gpu_count" in validate_package_contract_script,
        "final package-contract validation must compile the NCNNVulkan GPU public header",
    )
    require(
        "Runtime contract record" in release_document
        and "model: `strong-link`" in release_document
        and "install name: `@rpath/MoltenVK.framework/MoltenVK`" in release_document,
        "release documentation must record the NCNNVulkan runtime dependency contract",
    )
    require('path: "Artifacts/' not in package_swift, "committed Package.swift must not use repo-local artifact paths")
    require("FileManager.default.fileExists" not in package_swift, "committed Package.swift must not switch on local checkout state")
    _assert_no_hardcoded_deployment_targets(
        repo_root,
        PRODUCTION_SCRIPT_PATHS + PRODUCTION_WORKFLOW_PATHS,
    )
    _assert_package_platforms_cover_moltenvk_provider_floor(repo_root)

    source_acquisition = json.loads(read_text(repo_root / "scripts" / "spm" / "source_acquisition.json"))
    require(
        source_acquisition.get("upstream_tag_ref_prefix") == "refs/upstream-tags",
        "source acquisition contract must fetch into refs/upstream-tags",
    )
    require((repo_root / "scripts" / "spm" / "platforms.json").exists(), "platform metadata must exist")
    require((repo_root / "scripts" / "spm" / "current_release.json").exists(), "release metadata must exist")

    print("ncnn SOP conformance verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
