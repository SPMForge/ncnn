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
- `config/`
  - Declarative release metadata (`current_release.json`, `platforms.json`, `source_acquisition.json`, `moltenvk_dependency.json`)
- `scripts/`
  - Repo-local packaging, tag selection, source acquisition, manifest rendering, XCFramework validation, SOP conformance gate (`scripts/verify_sop_conformance.py`), and smoke-test helpers
- `tests/`
  - Top-level unit and workflow contract test suite
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
- If a package tag already exists but the GitHub Release is incomplete, reruns verify the tagged `Package.swift` and `config/current_release.json` before repairing assets or release metadata. Historical `release/*` branches are ignored by new alpha publishes.
- `Package.swift` should not be hand-edited for releases; the release pipeline regenerates it from `config/current_release.json`.
- New `NCNNVulkan` release builds strong-link `@rpath/MoltenVK.framework/MoltenVK`, and the generated SwiftPM package graph supplies `MoltenVK` through the `SPMForge/MoltenVK` dependency.
- Vulkan builds consume `MoltenVKHeaders-<version>.zip` as the C/C++ `Vulkan_INCLUDE_DIR`; ncnn packaging must not create app-side loader aliases or repo-local MoltenVK header overlays.
- Published `NCNNVulkan` public headers must compile for SwiftPM consumers without app-side `Vulkan_INCLUDE_DIR` settings.
- SwiftPM deployment platforms are package-level, so the package floors must cover the pinned MoltenVK provider floors. The current MoltenVK pin requires iOS 14.0 and tvOS 14.0 for generated `NCNNVulkan` manifests; preserving an iOS 13.0-only `NCNN` contract would require a separate Vulkan package.
- Development validation can override the staged MoltenVK prerelease with `prepare_moltenvk_dependency.py --version`, `SPMFORGE_MOLTENVK_VERSION`, or the validation workflow `moltenvk_version` input; local promotion uses `prepare_moltenvk_dependency.py --latest --write-pin` or `--version <tag> --write-pin`, and publish workflows read only the committed exact-version pin from `config/moltenvk_dependency.json` while resolving artifact checksums from GitHub release asset digests.
- The checked-in `Package.swift` still describes the already-published `1.0.20260113-alpha.5` artifacts; that legacy Vulkan archive weak-links `@rpath/libvulkan.dylib` and must not be relabeled as MoltenVK-backed without a new archive, tag, and checksum.
- Release gates fail if a newly built `ncnn_vulkan.framework` still links retired `libvulkan` loader install names or if the MoltenVK framework dependency is weak or missing.

## Documentation

- Wrapper package contract and workflow guide: [docs/how-to-build/swiftpm-binary-package.md](docs/how-to-build/swiftpm-binary-package.md)

## License

This repository and its distributed binary frameworks are licensed under the **BSD 3-Clause License** (see [LICENSE.txt](LICENSE.txt)), identical to upstream [`Tencent/ncnn`](https://github.com/Tencent/ncnn).

Third-party dependencies and math routines bundled within upstream ncnn are subject to their respective licenses as detailed in `LICENSE.txt` (including the zlib License and BSD-2-Clause).

## Release Input Identity

New releases record immutable upstream and wrapper input identity in
`config/release-inputs.json`. Scheduled and manual alpha use the same reuse/evaluate
policy and repository publication lock. See the
[repeat-publication SOP](docs/how-to-build/swiftpm-binary-package.md#immutable-source-and-repeat-publication-sop)
for source pinning, legacy tags, strict repair checks, and verification boundaries.

## CI stages and package consumption

Actions uses the same stage vocabulary across the wrapper repositories:
`Verify → Resolve → Build (product) → Validate Consumers → Publish → Summary`.
Validation runs omit publication. CPU/Vulkan products are separate branches;
platform slices remain grouped within each build job. Consumer jobs verify archive
transfer digests and test the final extracted XCFrameworks in Debug and Release.
A failed consumer blocks publication. Completed matching releases use the `Reuse`
path; metadata-only drift uses `Repair Metadata` without rebuilding.

Consume an accepted **package version tag**, rather than the default branch.
Alpha releases do not promote default-branch package metadata; a successful CI run
alone does not establish that the default-branch binary URLs are downloadable.
The Summary job records stage results and links to the run artifacts. Each build
artifact inventory records upstream commit, toolchain and archive SHA-256 values.

### Canonical release policy

This repository's scripts and tests own its executable package contract. The shared
policy references are [input identity and Alpha name allocation](https://github.com/RbBtSn0w/apple-skills/blob/main/app-develop/skills/apple-spm-binary-distribution/references/release-input-identity.md),
[publication and repair decisions](https://github.com/RbBtSn0w/apple-skills/blob/main/app-develop/skills/apple-spm-binary-distribution/references/release-repair-and-metadata-normalization.md),
and the [Actions stage contract](https://github.com/RbBtSn0w/apple-skills/blob/main/app-develop/skills/apple-spm-binary-distribution/references/ci-topologies.md).
Use accepted version tags; Alpha publication does not promote the default-branch manifest.
