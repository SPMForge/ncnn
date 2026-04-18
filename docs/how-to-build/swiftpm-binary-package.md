# Apple SwiftPM Binary Package

This document describes the dedicated SwiftPM binary packaging flow maintained on the `spm-binary` branch of `SPMForge/ncnn`.

## Overview

- Packaging model: dedicated packaging branch on `SPMForge/ncnn`
- Upstream source of truth: `Tencent/ncnn` tags in `YYYYMMDD` format
- Package tag format: `1.0.YYYYMMDD`
- Release metadata file: `scripts/spm/current_release.json`
- Manifest model: root `Package.swift` reads `scripts/spm/current_release.json`; release automation updates the metadata file instead of hand-editing checksums

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

The package does not publish standalone `openmp` or `glslang` binary targets.

## Release Automation

Two GitHub Actions workflows drive the package lifecycle:

- `.github/workflows/spm-binary-sync.yml`
  - Scheduled latest stable release detection
  - Optional manual rerun
- `.github/workflows/spm-binary-backfill.yml`
  - Manual backfill for a specific upstream tag
  - Optional overwrite of an existing package release

Each workflow:

1. Fetches upstream tags into `refs/upstream-tags/*`
2. Resolves the target upstream tag
3. Checks out the exact upstream source in a temporary worktree
4. Builds mergeable Apple XCFramework zips with repo-local Python scripts
5. Updates `scripts/spm/current_release.json`
6. Publishes the release assets on `SPMForge/ncnn`

## Local Maintenance Commands

Select the latest stable upstream tag:

```bash
python3 scripts/spm/select_upstream_tag.py --repo-root .
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

## Consumer Notes

- The generated binaries are mergeable libraries. Xcode consumers should use `MERGED_BINARY_TYPE=automatic`.
- `NCNNVulkan` is a distinct binary target from `NCNN`; do not assume that every Apple platform available in `NCNN` is also available in `NCNNVulkan`.
- `Package.swift` intentionally derives binary target URLs and checksums from `scripts/spm/current_release.json`; do not hand-edit `Package.swift` for new releases.
