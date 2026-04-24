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
- Alpha releases publish from `release/<package_tag>` commits so the tagged checkout carries the generated metadata without forcing those commits onto the default branch.
- Scheduled alpha publishes reuse the latest alpha tag when the rendered package contract still matches that tagged manifest, and advance to the next `X.Y.Z-alpha.N` only when packaging output changes. Manual alpha publishes use the same repair-or-advance rule.
- Stable promotions may update the default branch only when the manual workflow operator explicitly enables `publish_to_default_branch`; alpha paths never write the default branch.
- If `release/<package_tag>` already exists but the tag or GitHub Release is incomplete, reruns reuse the matching release-branch commit; a mismatched generated `Package.swift` or `scripts/spm/current_release.json` fails loudly.
- `Package.swift` should not be hand-edited for releases; the release pipeline regenerates it from `scripts/spm/current_release.json`.

## Documentation

- Wrapper package contract and workflow guide: [docs/how-to-build/swiftpm-binary-package.md](docs/how-to-build/swiftpm-binary-package.md)
