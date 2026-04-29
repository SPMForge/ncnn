# ncnn Apple SwiftPM Wrapper

This repository is an independent wrapper repository for publishing Apple SwiftPM binary distributions of `Tencent/ncnn`.

It does not carry the upstream source tree, upstream build matrix, or upstream contributor workflow. The repository only keeps the packaging contract, release automation, validation workflow, and minimal Apple build inputs required to produce GitHub Release assets for SwiftPM `.binaryTarget(...)` consumers.

## Scope

- Upstream source of truth: `https://github.com/Tencent/ncnn`
- Package contract owner: this repository
- Distribution channel: GitHub Release assets referenced by `Package.swift`
- Release model:
  - scheduled latest-upstream alpha publish
  - manual alpha or stable publish for a specific upstream tag
  - non-publishing validation workflow for branch and pull-request evidence

## Repository Contents

- `Package.swift`
  - Generated-at-release static manifest for SwiftPM consumers
- `scripts/spm/`
  - Repo-local packaging, tag selection, source acquisition, manifest rendering, XCFramework validation, and smoke-test helpers
- `.github/workflows/`
  - Shared publish core, scheduled alpha publish, manual publish, and non-publishing validation
- `toolchains/ios.toolchain.cmake`
  - Apple CMake toolchain input used by the wrapper build pipeline
- `docs/how-to-build/swiftpm-binary-package.md`
  - Operator documentation for the wrapper release contract

## Not In Scope

- Upstream `ncnn` source development
- Upstream issue templates or contributor onboarding
- Android, Linux, Windows, or generic cross-platform release packaging
- Mirroring Tencent/ncnn branch history inside this repository

## Operator Notes

- Release builds fetch upstream tags into `refs/upstream-tags/*`.
- Release and validation jobs export the requested upstream snapshot before building.
- Stable package tags require explicit manual intent.
- Alpha package tags point directly at immutable generated metadata commits so the tagged checkout carries the generated metadata without forcing those commits onto the default branch.
- Scheduled alpha publishes reuse the latest alpha tag when the rendered package contract still matches that tagged manifest, and advance to the next `X.Y.Z-alpha.N` only when packaging output changes. Manual alpha publishes use the same repair-or-advance rule.
- Stable promotions may update the default branch only when the manual workflow operator explicitly enables `publish_to_default_branch`; alpha paths never write the default branch.
- If a package tag already exists but the GitHub Release is incomplete, reruns verify the tagged `Package.swift` and `scripts/spm/current_release.json` before repairing assets or release metadata. Historical `release/*` branches are ignored by new alpha publishes.
- `Package.swift` should not be hand-edited for releases; the release pipeline regenerates it from `scripts/spm/current_release.json`.
- New `NCNNVulkan` release builds strong-link `@rpath/MoltenVK.framework/MoltenVK`, and the generated SwiftPM package graph supplies `MoltenVK` through the `SPMForge/MoltenVK` dependency.
- Vulkan builds consume `MoltenVKHeaders-<version>.zip` as the C/C++ `Vulkan_INCLUDE_DIR`; ncnn packaging must not create app-side loader aliases or repo-local MoltenVK header overlays.
- Published `NCNNVulkan` public headers must compile for SwiftPM consumers without app-side `Vulkan_INCLUDE_DIR` settings.
- SwiftPM deployment platforms are package-level, so the package floors must cover the pinned MoltenVK provider floors. The current MoltenVK pin requires iOS 14.0 and tvOS 14.0 for generated `NCNNVulkan` manifests; preserving an iOS 13.0-only `NCNN` contract would require a separate Vulkan package.
- Development validation can override the staged MoltenVK prerelease with `prepare_moltenvk_dependency.py --version`, `SPMFORGE_MOLTENVK_VERSION`, or the validation workflow `moltenvk_version` input; local promotion uses `prepare_moltenvk_dependency.py --latest --write-pin` or `--version <tag> --write-pin`, and publish workflows read only the committed exact-version pin from `scripts/spm/moltenvk_dependency.json` while resolving artifact checksums from GitHub release asset digests.
- The checked-in `Package.swift` still describes the already-published `1.0.20260113-alpha.5` artifacts; that legacy Vulkan archive weak-links `@rpath/libvulkan.dylib` and must not be relabeled as MoltenVK-backed without a new archive, tag, and checksum.
- Release gates fail if a newly built `ncnn_vulkan.framework` still links retired `libvulkan` loader install names or if the MoltenVK framework dependency is weak or missing.

## Documentation

- Wrapper package contract and workflow guide: [docs/how-to-build/swiftpm-binary-package.md](docs/how-to-build/swiftpm-binary-package.md)
