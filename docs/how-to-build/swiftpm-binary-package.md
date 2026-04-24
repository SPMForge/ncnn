# Apple SwiftPM Binary Package

This document describes the SwiftPM binary release flow maintained on the `main` branch of `SPMForge/ncnn`.

## Overview

- Target architecture: independent wrapper repo with a repo-local source acquisition contract and GitHub Release binary distribution
- Upstream source of truth: `Tencent/ncnn` tags in `YYYYMMDD` format
- Automated package tag format: `X.Y.Z-alpha.N`
- Manual publish mode: `alpha` or `stable`
- Current mapping rule: upstream tag `YYYYMMDD` becomes package version `1.0.YYYYMMDD`; automated sync starts from `1.0.YYYYMMDD-alpha.1`, reuses the latest alpha tag when the rendered package contract still matches that tagged manifest, and advances to the next `1.0.YYYYMMDD-alpha.N` only when packaging output changes; manual alpha follows the same repair-or-advance rule, and manual stable publishes `1.0.YYYYMMDD`
- Release metadata file: `scripts/spm/current_release.json`
- Platform metadata file: `scripts/spm/platforms.json`
- Source acquisition contract: `scripts/spm/source_acquisition.json`
- Manifest model: release automation regenerates root `Package.swift` from `scripts/spm/current_release.json`; published consumers read a static manifest instead of repo-local sidecar JSON files

Wrapper repo state:

- CI and release automation treat the checked-out repo as packaging logic only
- Real build input comes from an exported upstream snapshot resolved through the repo-local source acquisition contract
- The repository does not retain an in-repo upstream source tree

## Products

- `NCNN`
  - Binary target: `ncnn`
  - Module name: `ncnn`
  - Coverage: iOS, iOS Simulator, macOS, Mac Catalyst, tvOS, tvOS Simulator, watchOS, watchOS Simulator, visionOS, visionOS Simulator
- `NCNNVulkan`
  - Binary target: `ncnn_vulkan`
  - Module name: `ncnn_vulkan`
  - Coverage: iOS, iOS Simulator, macOS, Mac Catalyst, tvOS, tvOS Simulator, visionOS, visionOS Simulator
  - Caveat: watchOS and watchOS Simulator are intentionally excluded

Both variants are built with:

- `NCNN_SHARED_LIB=ON`
- `NCNN_OPENMP=ON`
- `NCNN_SIMPLEOMP=ON`

macOS packaging detail:

- Every Apple slice is wrapped as a framework bundle inside the XCFramework.
- iOS, simulator, Catalyst, tvOS, watchOS, and visionOS slices use a flat framework layout.
- The macOS XCFramework slice is wrapped as a native versioned framework bundle.
- Preserve `Versions/Current`, top-level symlinks, and `Resources/Info.plist`; do not flatten the macOS slice into a bare `.dylib` directory.
- Public headers and `Modules/module.modulemap` belong inside each framework slice. Do not keep a repo-level header tree as part of the package contract.
- Same-framework public header imports are rewritten during packaging to use framework-style includes such as `<ncnn/net.h>` or `<ncnn_vulkan/net.h>`.

The package does not publish standalone `openmp` or `glslang` binary targets.

## Release Automation

Two GitHub Actions workflows drive the package lifecycle:

- `.github/workflows/publish-latest-upstream-alpha.yml`
  - Scheduled latest stable release detection
  - Publishes the initial alpha prerelease for a new upstream tag as `X.Y.Z-alpha.1`
  - Reuses the latest alpha tag when the rendered package contract still matches that tagged manifest
  - Advances to the next `X.Y.Z-alpha.N` only when the newly rendered package contract differs from the latest alpha tag
  - Alpha publishes write the generated metadata onto a dedicated `release/<package_tag>` commit and do not update the default branch
  - Optional manual rerun
- `.github/workflows/publish-upstream-release-manually.yml`
  - Manual publish for a specific upstream tag
  - Requires choosing `alpha` or `stable`
  - Alpha uses the same repair-or-advance logic as scheduled sync without updating the default branch
  - Stable promotion publishes the stable package tag once validation is green and updates the default branch only when the operator explicitly enables `publish_to_default_branch`
- `.github/workflows/_publish-upstream-release-core.yml`
  - Shared publish core used by both publish entrypoints
  - Owns upstream tag resolution, source export, XCFramework build, manifest rendering, and GitHub Release publication
- `.github/workflows/validate-apple-release-pipeline.yml`
  - Minimal repo-maintainer CI for this fork
  - Validates workflow YAML, packaging tests, Apple platform preflight, real XCFramework builds, and the generated package contract without publishing
  - Supports optional manual reruns against a fixed upstream tag
The repository intentionally does not mirror Tencent/ncnn's full upstream CI matrix. Upstream platform/build coverage remains upstream's responsibility; this repo keeps only the workflows needed to validate and publish the Apple SwiftPM binary distribution contract.

Each workflow:

1. Fetches upstream tags into `refs/upstream-tags/*` through the repo-local source acquisition contract
2. Resolves the target upstream tag
3. Exports the exact upstream source snapshot into a temporary worktree
4. Builds mergeable Apple XCFramework zips with repo-local Python scripts
5. Runs `scripts/spm/preflight_apple_platforms.py` so missing Apple platform support fails before long archive jobs start
6. Validates `MergeableMetadata`, binary paths, required platforms, and `vtool` platform identity
7. Validates the generated package contract from the same fresh build metadata with `scripts/spm/validate_package_contract.py` or `swift package dump-package`
8. Renders `scripts/spm/current_release.json` and `Package.swift` for the final package tag
9. Creates or reuses a `release/<package_tag>` commit so the tag checkout contains the generated metadata
10. Publishes the release assets from GitHub Releases; alpha paths do not update the default branch, while stable promotion may update the default branch with the tagged commit only when `publish_to_default_branch` is explicitly enabled

## Local Maintenance Commands

Select the latest stable upstream tag:

```bash
python3 scripts/spm/select_upstream_tag.py --repo-root .
```

Resolve the next manual alpha tag for a specific upstream tag:

```bash
python3 scripts/spm/select_upstream_tag.py \
  --repo-root . \
  --explicit-tag 20260113 \
  --release-channel alpha
```

Resolve the stable package tag for a specific upstream tag:

```bash
python3 scripts/spm/select_upstream_tag.py \
  --repo-root . \
  --explicit-tag 20260113 \
  --release-channel stable
```

Build the CPU-only package locally:

```bash
python3 scripts/spm/build_apple_xcframework.py \
  --variant ncnn \
  --upstream-tag 20260113 \
  --source-root /path/to/upstream-source-tree \
  --output-dir /tmp/ncnn-spm
```

Build the Vulkan package locally:

```bash
python3 scripts/spm/build_apple_xcframework.py \
  --variant ncnn_vulkan \
  --upstream-tag 20260113 \
  --source-root /path/to/upstream-source-tree \
  --output-dir /tmp/ncnn-spm
```

Merge release metadata after building both variants:

```bash
python3 scripts/spm/render_package.py \
  --release-metadata /tmp/ncnn-spm/ncnn/ncnn.release.json \
  --release-metadata /tmp/ncnn-spm/ncnn_vulkan/ncnn_vulkan.release.json \
  --current-release-json scripts/spm/current_release.json
```

Validate the current manifest:

```bash
swift package dump-package
```

Fetch upstream tags through the wrapper-repo contract:

```bash
python3 scripts/spm/source_acquisition.py fetch-tags --repo-root .
```

Export a fixed upstream snapshot for local reproduction:

```bash
python3 scripts/spm/source_acquisition.py export-source \
  --repo-root . \
  --upstream-tag 20260113 \
  --destination /tmp/ncnn-upstream-source
```

Validate the built XCFramework before publishing:

```bash
python3 scripts/spm/validate_mergeable_xcframework.py \
  /tmp/ncnn-spm/ncnn/ncnn-20260113-apple.xcframework.zip \
  --require-platform ios \
  --require-platform ios-simulator \
  --require-platform macos \
  --require-platform ios-maccatalyst \
  --require-platform tvos \
  --require-platform tvos-simulator \
  --require-platform watchos \
  --require-platform watchos-simulator \
  --require-platform xros \
  --require-platform xros-simulator
```

Run the Apple platform preflight used by CI:

```bash
preflight_args=(
  --required-platform ios
  --required-platform ios-simulator
  --required-platform macos
  --required-platform ios-maccatalyst
  --required-platform tvos
  --required-platform tvos-simulator
  --required-platform watchos
  --required-platform watchos-simulator
  --required-platform xros
  --required-platform xros-simulator
)
python3 scripts/spm/preflight_apple_platforms.py \
  --variant ncnn \
  "${preflight_args[@]}"
```

Validate the generated package contract from fresh artifact metadata:

```bash
python3 scripts/spm/validate_package_contract.py \
  --repo-root . \
  --release-metadata /tmp/ncnn-spm/ncnn/ncnn.release.json \
  --release-metadata /tmp/ncnn-spm/ncnn_vulkan/ncnn_vulkan.release.json \
  --release-archive /tmp/ncnn-spm/ncnn/ncnn-20260113-apple.xcframework.zip \
  --release-archive /tmp/ncnn-spm/ncnn_vulkan/ncnn-20260113-apple-vulkan.xcframework.zip
```

## CI Cache Topology

- Compiler cache: `ccache`
- Persisted cache path: `${{ github.workspace }}/.ccache`
- Homebrew download cache path: `${{ github.workspace }}/.homebrew-cache`
- Persisted with: `actions/cache@v5`
- Cache key dimensions: runner OS, cache schema version, resolved Xcode version, artifact variant, upstream tag
- Restore strategy: exact key first, then same Xcode plus same variant, then same Xcode only
- Not cached by default: `DerivedData`, `ArchiveIntermediates`, or other opaque Xcode build directories

Why this repo uses this shape:

- The expensive part of CI is repeated C and C++ compilation across Apple slices
- The next most common cold-start cost is downloading the `ccache` Homebrew bottle; the workflow persists Homebrew downloads separately so repeated runs do not redownload them
- `ccache` is easier to invalidate and reason about than directory-level Xcode caches
- Wrapper-based compiler injection keeps the cache behavior repo-local and reviewable

What to verify in CI logs:

- `restore-ccache` prints either `Cache restored from key` or `Cache not found`
- `restore-homebrew-download-cache` prints either `Cache restored from key` or `Cache not found`
- `build-ccache-stats` prints hit and miss counts after a real build
- `Post restore-ccache` prints either `Cache saved with key` on a cold run or `Cache hit occurred on the primary key` on a warm run

## Validation Safeguards

- Validation CI now checks the generated package contract from the same artifact set that produced the XCFramework zips, including a local consumer compile against the final multi-product package; PR validation should not wait until the publishing workflow to discover manifest drift.
- Apple platform support is preflighted before archive work starts; missing `visionOS`, `watchOS`, or other platform support should fail early with an `xcodebuild -downloadPlatform ...` hint instead of failing at the end of a long archive job.
- Deployment targets remain centralized in `scripts/spm/platforms.json`; the preflight step treats drift between workflow platform lists and the variant contract as a CI error.
- XCFramework validation rejects a flattened macOS framework slice; the macOS bundle must retain its versioned framework layout.
- XCFramework validation also rejects exported framework headers that still use quoted or non-framework same-header imports.

## Consumer Notes

- The generated binaries are mergeable libraries. Xcode consumers should use `MERGED_BINARY_TYPE=automatic`.
- The repo-local smoke test validates Debug consumption with `swift build` and Release consumption with `xcodebuild ... MERGED_BINARY_TYPE=automatic`, using framework-style public header imports.
- The final package-contract gate repeats consumer validation from the aggregated package root, not only from per-variant standalone XCFrameworks.
- `NCNNVulkan` is a distinct binary target from `NCNN`; do not assume that every Apple platform available in `NCNN` is also available in `NCNNVulkan`.
- `Package.swift` is regenerated from `scripts/spm/current_release.json` during release automation; do not hand-edit `Package.swift` for new releases.
- Release CI does not build from any checked-in upstream source tree; it builds from the exported upstream snapshot resolved by `scripts/spm/source_acquisition.json`.
- Automated SwiftPM package tags are always GitHub prereleases in the alpha channel.
- Alpha release commits do not update the default branch; they are tagged from `release/<package_tag>` so the alpha checkout still contains the generated metadata.
- Manual publishing must explicitly choose `alpha` or `stable`; stable default-branch writes additionally require the boolean `publish_to_default_branch` operator choice. Repeated packaging fixes for the same upstream snapshot must advance `N`; stable promotion must publish the exact stable package tag once, not mutate an existing alpha release.
- If `release/<package_tag>` already exists but the package tag or GitHub Release was not completed, reruns reuse the matching release-branch commit. If the branch commit does not match the freshly generated `Package.swift` and `scripts/spm/current_release.json`, the workflow fails loudly instead of overwriting it.
