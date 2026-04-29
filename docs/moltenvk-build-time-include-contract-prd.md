# MoltenVK Build-Time Include Contract PRD

Status: implemented upstream in `SPMForge/MoltenVK` `1.4.1-alpha.6`. The provider now publishes `MoltenVKHeaders-1.4.1-alpha.6.zip`, whose extracted `include/` directory is the downstream C/C++ build-time include root.

## Summary

`SPMForge/MoltenVK` is valid as an Apple framework provider, but it also needs a documented and CI-verified build-time include contract for downstream C and C++ projects that consume Vulkan through CMake-style inputs.

This PRD describes the MoltenVK-side change needed so downstream packages such as `SPMForge/ncnn` can build against the SwiftPM-supplied `MoltenVK.framework` without creating ad hoc include overlays.

## Problem

`SPMForge/ncnn` builds the `NCNNVulkan` product from upstream C++ sources. The upstream code consumes Vulkan as a C API and includes headers through the Vulkan SDK-style surface:

```cpp
#include <vulkan/vulkan.h>
```

Before `1.4.1-alpha.6`, the MoltenVK framework artifact contained this header at:

```text
MoltenVK.framework/Headers/vulkan/vulkan.h
```

However, that header internally includes framework-style paths:

```cpp
#include <MoltenVK/vulkan/vk_platform.h>
#include <MoltenVK/vulkan/vulkan_core.h>
```

When a downstream CMake build passes:

```text
Vulkan_INCLUDE_DIR=MoltenVK.framework/Headers
```

the compiler can find `<vulkan/vulkan.h>`, but it cannot resolve `<MoltenVK/vulkan/...>`. This breaks downstream C/C++ builds even though the framework is otherwise usable through SwiftPM/framework consumption.

## Observed Failure

`SPMForge/ncnn` CI run `validate-apple-release-pipeline #30` failed in the `ncnn_vulkan` build step with:

```text
fatal error: 'MoltenVK/vulkan/vk_platform.h' file not found
```

The failure happened during source compilation before Mach-O dependency validation. It was not a runtime loader issue and not a SwiftPM dependency resolution issue.

## Product Boundary

MoltenVK has two distinct consumer surfaces:

| Surface | Consumer type | Expected use |
| --- | --- | --- |
| Apple framework / SwiftPM product | Swift, Objective-C, Xcode framework consumers | `import MoltenVK`, `@import MoltenVK;`, or `#include <MoltenVK/...>` |
| Vulkan C API build input | C/C++ projects, CMake `find_package(Vulkan)` style consumers | `#include <vulkan/vulkan.h>` plus a link target pointing at `MoltenVK.framework/MoltenVK` |

Both surfaces can be valid at the same time. The issue was that the framework artifact alone did not provide one self-contained include root that satisfies the Vulkan C API surface and MoltenVK's framework-style self-includes together.

## Goals

- Provide a stable build-time include contract for C and C++ downstream packages.
- Preserve `MoltenVK.framework` as the runtime provider framework.
- Keep the SwiftPM product identity as `MoltenVK`.
- Let downstream CMake builds pass one documented include root and one framework binary path.
- Add CI validation that proves the published artifact can compile a minimal Vulkan C API consumer.

## Non-Goals

- Do not ship or promise `libvulkan.dylib` or `libvulkan.1.dylib`.
- Do not change MoltenVK's runtime dependency model from `none`.
- Do not require app targets to create runtime aliases or use app-side `dlopen()` workarounds.
- Do not rename the SwiftPM product or Apple framework from `MoltenVK` to `vulkan`.
- Do not make downstream packages patch MoltenVK headers.

## Required Contract

MoltenVK should publish and document a build-time include root that satisfies both of these includes in the same translation unit:

```c
#include <vulkan/vulkan.h>
#include <MoltenVK/vulkan/vk_platform.h>
```

That include root may be implemented as one of the following:

- a generated include overlay inside the release artifact,
- a package-local support target that exposes the overlay,
- a documented CMake package/config output that gives downstreams the correct include directories,
- or a framework layout adjustment that makes `MoltenVK.framework/Headers` self-contained for both include styles.

The exact implementation can stay MoltenVK-local, but the exported contract must be explicit and verified.

## Recommended Implementation

Implemented minimal contract:

1. Publish `MoltenVKHeaders-<version>.zip` alongside `MoltenVK-<version>.xcframework.zip`.
2. Expose both paths from the same extracted include root:

```text
<include-root>/vulkan
<include-root>/MoltenVK
```

3. Document that downstream C/C++ builds should use:

```text
Vulkan_INCLUDE_DIR=<include-root>
Vulkan_LIBRARY=<path-to-MoltenVK.framework/MoltenVK>
```

This moves the responsibility to the provider package and makes the contract stable.

## CI Acceptance Gates

MoltenVK CI should validate the final published artifact, not an intermediate build tree.

Required checks:

1. SwiftPM/framework consumer check:

```swift
import MoltenVK
```

2. C API include check:

```c
#include <vulkan/vulkan.h>
int main(void) { return 0; }
```

Compile it with the documented include root:

```bash
clang -fsyntax-only -I "$MOLTENVK_INCLUDE_ROOT" probe.c
```

3. Framework-style include check:

```c
#include <MoltenVK/vulkan/vk_platform.h>
int main(void) { return 0; }
```

Compile it with the same include root:

```bash
clang -fsyntax-only -I "$MOLTENVK_INCLUDE_ROOT" probe.c
```

4. Runtime contract check:

```bash
otool -L MoltenVK.framework/MoltenVK
```

The package should continue to avoid promising `libvulkan.dylib` or `libvulkan.1.dylib` unless it intentionally ships a loader artifact under a separate contract.

## Downstream Impact

After `SPMForge/MoltenVK` `1.4.1-alpha.6`, downstream packages such as `SPMForge/ncnn` can replace local include-overlay generation with the provider's documented build-time include root.

Expected downstream behavior:

- `NCNNVulkan` continues to strong-link `@rpath/MoltenVK.framework/MoltenVK`.
- SwiftPM consumers receive `MoltenVK.framework` through the package dependency graph.
- CMake build steps consume the provider-declared include root instead of guessing `MoltenVK.framework/Headers`.
- CI still proves Mach-O dependency shape, SwiftPM consumer closure, and Vulkan feature-path behavior.

## Release Notes Requirement

The MoltenVK release notes should state:

- the package remains a provider framework package,
- it does not ship a Vulkan loader dylib,
- it now provides a documented build-time include contract for C/C++ Vulkan API consumers,
- and downstream CMake builds should use the documented include root rather than directly assuming `MoltenVK.framework/Headers` is sufficient.

## Definition of Done

- The final MoltenVK release artifact exposes a documented include root.
- Both `<vulkan/vulkan.h>` and `<MoltenVK/vulkan/vk_platform.h>` compile with that root.
- SwiftPM framework consumers still import `MoltenVK`.
- Runtime dependency model remains `none`.
- No `libvulkan.dylib` or `libvulkan.1.dylib` runtime promise is introduced.
- `SPMForge/ncnn` can build `NCNNVulkan` without a repo-local MoltenVK include workaround once it consumes the updated MoltenVK contract.
