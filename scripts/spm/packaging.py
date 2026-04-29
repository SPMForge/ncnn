from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re


_UPSTREAM_TAG_PATTERN = re.compile(r"^\d{8}$")
_ALPHA_NUMBER_PATTERN = re.compile(r"^[1-9]\d*$")


@dataclass(frozen=True)
class Platform:
    name: str
    swiftpm_platform: str
    cmake_platform: str
    xcode_destination: str
    archs: tuple[str, ...]
    deployment_target: str


@dataclass(frozen=True)
class Variant:
    target_name: str
    product_name: str
    asset_suffix: str
    module_name: str
    platforms: tuple[Platform, ...]
    runtime_dependency_model: str = "none"
    runtime_dependency_supplier: str = "none"
    runtime_dependencies: tuple[str, ...] = ()
    strong_runtime_dependencies: tuple[str, ...] = ()
    weak_runtime_dependencies: tuple[str, ...] = ()
    forbidden_runtime_dependencies: tuple[str, ...] = ()
    swiftpm_dependencies: tuple["SwiftPackageDependency", ...] = ()
    runtime_support_target: "RuntimeSupportTarget | None" = None


@dataclass(frozen=True)
class SwiftPackageDependency:
    package_name: str
    url: str
    exact_version: str


@dataclass(frozen=True)
class SwiftPackageProductDependency:
    product_name: str
    package_name: str


@dataclass(frozen=True)
class RuntimeSupportTarget:
    target_name: str
    path: str
    product_dependencies: tuple[SwiftPackageProductDependency, ...]


@dataclass(frozen=True)
class ReleaseAsset:
    variant: Variant
    upstream_tag: str
    package_tag: str
    checksum: str
    runtime_dependency_model: str | None = None
    runtime_dependency_supplier: str | None = None
    runtime_dependencies: tuple[str, ...] | None = None
    strong_runtime_dependencies: tuple[str, ...] | None = None
    weak_runtime_dependencies: tuple[str, ...] | None = None
    forbidden_runtime_dependencies: tuple[str, ...] | None = None


@dataclass(frozen=True)
class BuildArtifactMetadata:
    release_asset: ReleaseAsset
    artifact_path: str


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = Path(__file__).resolve().parent
DEFAULT_PACKAGE_NAME = "ncnn"
DEFAULT_OWNER = "SPMForge"
DEFAULT_REPO = "ncnn"
TOOLCHAIN_FILE = REPO_ROOT / "toolchains" / "ios.toolchain.cmake"
CURRENT_RELEASE_METADATA_PATH = SCRIPTS_ROOT / "current_release.json"
PLATFORM_METADATA_PATH = SCRIPTS_ROOT / "platforms.json"
MOLTENVK_DEPENDENCY_CONFIG_PATH = SCRIPTS_ROOT / "moltenvk_dependency.json"
PACKAGE_SWIFT_PATH = REPO_ROOT / "Package.swift"
BUILD_ARTIFACT_METADATA_SCHEMA_VERSION = 2
MOLTENVK_VERSION_ENV = "SPMFORGE_MOLTENVK_VERSION"
MOLTENVK_ARTIFACT_CHECKSUM_ENV = "SPMFORGE_MOLTENVK_ARTIFACT_CHECKSUM"
MOLTENVK_HEADERS_ARTIFACT_CHECKSUM_ENV = "SPMFORGE_MOLTENVK_HEADERS_ARTIFACT_CHECKSUM"


def _load_moltenvk_dependency_config() -> dict[str, str]:
    payload = json.loads(MOLTENVK_DEPENDENCY_CONFIG_PATH.read_text())
    required_fields = ("package_name", "url", "version")
    optional_fields = ("xcframework_checksum", "headers_checksum")
    result = {}
    for field_name in required_fields:
        value = payload.get(field_name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"invalid {field_name} in {MOLTENVK_DEPENDENCY_CONFIG_PATH}")
        result[field_name] = value
    for field_name in optional_fields:
        value = payload.get(field_name, "")
        if not isinstance(value, str):
            raise ValueError(f"invalid {field_name} in {MOLTENVK_DEPENDENCY_CONFIG_PATH}")
        result[field_name] = value
    return result


MOLTENVK_DEPENDENCY_CONFIG = _load_moltenvk_dependency_config()
MOLTENVK_PINNED_VERSION = MOLTENVK_DEPENDENCY_CONFIG["version"]
MOLTENVK_VERSION = os.environ.get(MOLTENVK_VERSION_ENV, "").strip() or MOLTENVK_PINNED_VERSION
MOLTENVK_PACKAGE = SwiftPackageDependency(
    package_name=MOLTENVK_DEPENDENCY_CONFIG["package_name"],
    url=MOLTENVK_DEPENDENCY_CONFIG["url"],
    exact_version=MOLTENVK_VERSION,
)
MOLTENVK_PRODUCT = SwiftPackageProductDependency(
    product_name="MoltenVK",
    package_name=MOLTENVK_DEPENDENCY_CONFIG["package_name"],
)
MOLTENVK_RUNTIME_SUPPORT_TARGET = RuntimeSupportTarget(
    target_name="ncnn_vulkan_runtime_support",
    path="Sources/ncnn_vulkan_runtime_support",
    product_dependencies=(MOLTENVK_PRODUCT,),
)
MOLTENVK_ARTIFACT_URL = (
    "https://github.com/SPMForge/MoltenVK/releases/download/"
    f"{MOLTENVK_PACKAGE.exact_version}/MoltenVK-{MOLTENVK_PACKAGE.exact_version}.xcframework.zip"
)
MOLTENVK_ARTIFACT_CHECKSUM = (
    os.environ.get(MOLTENVK_ARTIFACT_CHECKSUM_ENV, "").strip()
    or (MOLTENVK_DEPENDENCY_CONFIG["xcframework_checksum"] if MOLTENVK_VERSION == MOLTENVK_PINNED_VERSION else "")
)
MOLTENVK_HEADERS_ARTIFACT_URL = (
    "https://github.com/SPMForge/MoltenVK/releases/download/"
    f"{MOLTENVK_PACKAGE.exact_version}/MoltenVKHeaders-{MOLTENVK_PACKAGE.exact_version}.zip"
)
MOLTENVK_HEADERS_ARTIFACT_CHECKSUM = (
    os.environ.get(MOLTENVK_HEADERS_ARTIFACT_CHECKSUM_ENV, "").strip()
    or (MOLTENVK_DEPENDENCY_CONFIG["headers_checksum"] if MOLTENVK_VERSION == MOLTENVK_PINNED_VERSION else "")
)
MOLTENVK_STRONG_INSTALL_NAME = "@rpath/MoltenVK.framework/MoltenVK"
RETIRED_VULKAN_LOADER_INSTALL_NAMES = (
    "@rpath/libvulkan.dylib",
    "@rpath/libvulkan.1.dylib",
)
PACKAGE_PLATFORM_ORDER = ("ios", "macos", "ios-maccatalyst", "tvos", "watchos", "xros")
PACKAGE_PLATFORM_FUNCTIONS = {
    "ios": "iOS",
    "macos": "macOS",
    "ios-maccatalyst": "macCatalyst",
    "tvos": "tvOS",
    "watchos": "watchOS",
    "xros": "visionOS",
}


def _load_platform_metadata() -> dict[str, dict[str, str]]:
    payload = json.loads(PLATFORM_METADATA_PATH.read_text())
    package_platforms = payload.get("package_platforms")
    if not isinstance(package_platforms, dict):
        raise ValueError(f"invalid platform metadata in {PLATFORM_METADATA_PATH}")
    return {"package_platforms": {str(key): str(value) for key, value in package_platforms.items()}}


PLATFORM_METADATA = _load_platform_metadata()
PACKAGE_PLATFORM_DEPLOYMENT_TARGETS = PLATFORM_METADATA["package_platforms"]

CPU_VARIANT = Variant(
    target_name="ncnn",
    product_name="NCNN",
    asset_suffix="apple",
    module_name="ncnn",
    platforms=(
        Platform("iOS", "ios", "OS64", "generic/platform=iOS", ("arm64",), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["ios"]),
        Platform("iOS Simulator", "ios-simulator", "SIMULATORARM64", "generic/platform=iOS Simulator", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["ios"]),
        Platform("macOS", "macos", "MAC", "generic/platform=macOS", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["macos"]),
        Platform("Mac Catalyst", "ios-maccatalyst", "MAC_CATALYST", "generic/platform=macOS,variant=Mac Catalyst", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["ios-maccatalyst"]),
        Platform("tvOS", "tvos", "TVOS", "generic/platform=tvOS", ("arm64",), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["tvos"]),
        Platform("tvOS Simulator", "tvos-simulator", "SIMULATORARM64_TVOS", "generic/platform=tvOS Simulator", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["tvos"]),
        Platform("watchOS", "watchos", "WATCHOS", "generic/platform=watchOS", ("arm64", "arm64_32"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["watchos"]),
        Platform("watchOS Simulator", "watchos-simulator", "SIMULATOR_WATCHOS", "generic/platform=watchOS Simulator", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["watchos"]),
        Platform("visionOS", "xros", "VISIONOS", "generic/platform=visionOS", ("arm64",), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["xros"]),
        Platform("visionOS Simulator", "xros-simulator", "SIMULATOR_VISIONOS", "generic/platform=visionOS Simulator", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["xros"]),
    ),
)

VULKAN_VARIANT = Variant(
    target_name="ncnn_vulkan",
    product_name="NCNNVulkan",
    asset_suffix="apple-vulkan",
    module_name="ncnn_vulkan",
    platforms=(
        Platform("iOS", "ios", "OS64", "generic/platform=iOS", ("arm64",), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["ios"]),
        Platform("iOS Simulator", "ios-simulator", "SIMULATORARM64", "generic/platform=iOS Simulator", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["ios"]),
        Platform("macOS", "macos", "MAC", "generic/platform=macOS", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["macos"]),
        Platform("tvOS", "tvos", "TVOS", "generic/platform=tvOS", ("arm64",), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["tvos"]),
        Platform("tvOS Simulator", "tvos-simulator", "SIMULATORARM64_TVOS", "generic/platform=tvOS Simulator", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["tvos"]),
        Platform("visionOS", "xros", "VISIONOS", "generic/platform=visionOS", ("arm64",), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["xros"]),
        Platform("visionOS Simulator", "xros-simulator", "SIMULATOR_VISIONOS", "generic/platform=visionOS Simulator", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["xros"]),
    ),
    runtime_dependency_model="strong-link",
    runtime_dependency_supplier="package:MoltenVK/product:MoltenVK",
    runtime_dependencies=(MOLTENVK_STRONG_INSTALL_NAME,),
    strong_runtime_dependencies=(MOLTENVK_STRONG_INSTALL_NAME,),
    forbidden_runtime_dependencies=RETIRED_VULKAN_LOADER_INSTALL_NAMES,
    swiftpm_dependencies=(MOLTENVK_PACKAGE,),
    runtime_support_target=MOLTENVK_RUNTIME_SUPPORT_TARGET,
)

VARIANTS = (CPU_VARIANT, VULKAN_VARIANT)
VARIANTS_BY_TARGET = {variant.target_name: variant for variant in VARIANTS}


def _validate_upstream_tag(upstream_tag: str) -> None:
    if not _UPSTREAM_TAG_PATTERN.match(upstream_tag):
        raise ValueError(f"unsupported upstream tag format: {upstream_tag}")


def package_version_for_upstream_tag(upstream_tag: str) -> str:
    _validate_upstream_tag(upstream_tag)
    return f"1.0.{upstream_tag}"


def stable_package_tag_for_upstream_tag(upstream_tag: str) -> str:
    return package_version_for_upstream_tag(upstream_tag)


def package_tag_for_upstream_tag(upstream_tag: str, alpha_number: int = 1) -> str:
    package_version = stable_package_tag_for_upstream_tag(upstream_tag)
    alpha_number_string = str(alpha_number)
    if not _ALPHA_NUMBER_PATTERN.match(alpha_number_string):
        raise ValueError(f"unsupported alpha number: {alpha_number}")
    return f"{package_version}-alpha.{alpha_number_string}"


def next_alpha_number_for_upstream_tag(upstream_tag: str, refs: list[str]) -> int:
    package_version = package_version_for_upstream_tag(upstream_tag)
    tag_prefix = f"{package_version}-alpha."
    existing_alpha_numbers = []

    for ref in refs:
        ref_name = ref.removeprefix("refs/tags/")
        if not ref_name.startswith(tag_prefix):
            continue
        alpha_suffix = ref_name[len(tag_prefix) :]
        if _ALPHA_NUMBER_PATTERN.match(alpha_suffix):
            existing_alpha_numbers.append(int(alpha_suffix))

    if not existing_alpha_numbers:
        return 1
    return max(existing_alpha_numbers) + 1


def latest_alpha_package_tag_for_upstream_tag(upstream_tag: str, refs: list[str]) -> str | None:
    package_version = package_version_for_upstream_tag(upstream_tag)
    tag_prefix = f"{package_version}-alpha."
    latest_alpha_number: int | None = None

    for ref in refs:
        ref_name = ref.removeprefix("refs/tags/")
        if not ref_name.startswith(tag_prefix):
            continue
        alpha_suffix = ref_name[len(tag_prefix) :]
        if not _ALPHA_NUMBER_PATTERN.match(alpha_suffix):
            continue
        alpha_number = int(alpha_suffix)
        if latest_alpha_number is None or alpha_number > latest_alpha_number:
            latest_alpha_number = alpha_number

    if latest_alpha_number is None:
        return None
    return package_tag_for_upstream_tag(upstream_tag, alpha_number=latest_alpha_number)


def asset_name_for_variant(variant: Variant, upstream_tag: str) -> str:
    if not _UPSTREAM_TAG_PATTERN.match(upstream_tag):
        raise ValueError(f"unsupported upstream tag format: {upstream_tag}")
    return f"ncnn-{upstream_tag}-{variant.asset_suffix}.xcframework.zip"


def release_url(owner: str, repo: str, package_tag: str, variant: Variant, upstream_tag: str) -> str:
    asset_name = asset_name_for_variant(variant, upstream_tag)
    return f"https://github.com/{owner}/{repo}/releases/download/{package_tag}/{asset_name}"


def variant_for_target_name(target_name: str) -> Variant:
    try:
        return VARIANTS_BY_TARGET[target_name]
    except KeyError as error:
        raise ValueError(f"unsupported variant target name: {target_name}") from error


def _optional_tuple_field(payload: dict[str, object], field_name: str) -> tuple[str, ...] | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"invalid {field_name} in release metadata")
    return tuple(value)


def _optional_string_field(payload: dict[str, object], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid {field_name} in release metadata")
    return value


def release_asset_from_current_release_record(payload: dict[str, object]) -> ReleaseAsset:
    target_name = payload.get("target_name")
    upstream_tag = payload.get("upstream_tag")
    package_tag = payload.get("package_tag")
    checksum = payload.get("checksum")
    if not isinstance(target_name, str) or not target_name:
        raise ValueError("invalid target_name in release metadata")
    if not isinstance(upstream_tag, str) or not upstream_tag:
        raise ValueError("invalid upstream_tag in release metadata")
    if not isinstance(package_tag, str) or not package_tag:
        raise ValueError("invalid package_tag in release metadata")
    if not isinstance(checksum, str) or not checksum:
        raise ValueError("invalid checksum in release metadata")
    return ReleaseAsset(
        variant=variant_for_target_name(target_name),
        upstream_tag=upstream_tag,
        package_tag=package_tag,
        checksum=checksum,
        runtime_dependency_model=_optional_string_field(payload, "runtime_dependency_model"),
        runtime_dependency_supplier=_optional_string_field(payload, "runtime_dependency_supplier"),
        runtime_dependencies=_optional_tuple_field(payload, "runtime_dependencies"),
        strong_runtime_dependencies=_optional_tuple_field(payload, "strong_runtime_dependencies"),
        weak_runtime_dependencies=_optional_tuple_field(payload, "weak_runtime_dependencies"),
        forbidden_runtime_dependencies=_optional_tuple_field(payload, "forbidden_runtime_dependencies"),
    )


def required_weak_dependencies_for_variant(variant: Variant) -> list[str]:
    return list(variant.weak_runtime_dependencies)


def required_dependencies_for_variant(variant: Variant) -> list[str]:
    return list(variant.runtime_dependencies)


def required_strong_dependencies_for_variant(variant: Variant) -> list[str]:
    return list(variant.strong_runtime_dependencies)


def forbidden_dependencies_for_variant(variant: Variant) -> list[str]:
    return list(variant.forbidden_runtime_dependencies)


def _release_runtime_dependency_model(release: ReleaseAsset) -> str:
    return release.runtime_dependency_model or release.variant.runtime_dependency_model


def _release_uses_variant_runtime_closure(release: ReleaseAsset) -> bool:
    return _release_runtime_dependency_model(release) == release.variant.runtime_dependency_model


def _swiftpm_dependencies_for_release(release: ReleaseAsset) -> tuple[SwiftPackageDependency, ...]:
    if not _release_uses_variant_runtime_closure(release):
        return ()
    return release.variant.swiftpm_dependencies


def _runtime_support_target_for_release(release: ReleaseAsset) -> RuntimeSupportTarget | None:
    if not _release_uses_variant_runtime_closure(release):
        return None
    return release.variant.runtime_support_target


def product_targets_for_release(release: ReleaseAsset) -> list[str]:
    targets = [release.variant.target_name]
    support_target = _runtime_support_target_for_release(release)
    if support_target is not None:
        targets.append(support_target.target_name)
    return targets


def _unique_swiftpm_dependencies(releases: list[ReleaseAsset]) -> list[SwiftPackageDependency]:
    dependencies: dict[str, SwiftPackageDependency] = {}
    for release in releases:
        for dependency in _swiftpm_dependencies_for_release(release):
            existing_dependency = dependencies.get(dependency.package_name)
            if existing_dependency is not None and existing_dependency != dependency:
                raise ValueError(f"conflicting SwiftPM dependency contract for {dependency.package_name}")
            dependencies[dependency.package_name] = dependency
    return [dependencies[key] for key in sorted(dependencies)]


def _runtime_support_targets(releases: list[ReleaseAsset]) -> list[RuntimeSupportTarget]:
    targets: dict[str, RuntimeSupportTarget] = {}
    for release in releases:
        support_target = _runtime_support_target_for_release(release)
        if support_target is None:
            continue
        existing_target = targets.get(support_target.target_name)
        if existing_target is not None and existing_target != support_target:
            raise ValueError(f"conflicting runtime support target contract for {support_target.target_name}")
        targets[support_target.target_name] = support_target
    return [targets[key] for key in sorted(targets)]


def _render_product_dependency(dependency: SwiftPackageProductDependency) -> str:
    return f'.product(name: "{dependency.product_name}", package: "{dependency.package_name}")'


def write_runtime_support_sources(package_root: Path, releases: list[ReleaseAsset]) -> None:
    for support_target in _runtime_support_targets(releases):
        source_root = package_root / support_target.path
        source_root.mkdir(parents=True, exist_ok=True)
        include_root = source_root / "include"
        include_root.mkdir(parents=True, exist_ok=True)
        anchor_name = support_target.target_name.replace("-", "_")
        header_name = f"{support_target.target_name}.h"
        header_guard = f"{anchor_name.upper()}_H"
        (include_root / header_name).write_text(
            f"#ifndef {header_guard}\n"
            f"#define {header_guard}\n"
            "\n"
            f"void {anchor_name}_anchor(void);\n"
            "\n"
            f"#endif /* {header_guard} */\n"
        )
        (source_root / "runtime_anchor.c").write_text(
            f'#include "{header_name}"\n'
            "\n"
            f"void {anchor_name}_anchor(void) {{}}\n"
        )


def render_package_platforms() -> list[str]:
    return [
        f'        .{PACKAGE_PLATFORM_FUNCTIONS[platform_key]}("{PACKAGE_PLATFORM_DEPLOYMENT_TARGETS[platform_key]}"),'
        for platform_key in PACKAGE_PLATFORM_ORDER
    ]


def _render_package_manifest(
    package_name: str,
    releases: list[ReleaseAsset],
    binary_target_lines: list[list[str]],
) -> str:
    swiftpm_dependencies = _unique_swiftpm_dependencies(releases)
    runtime_support_targets = _runtime_support_targets(releases)
    lines = [
        "// swift-tools-version: 5.9",
        "",
        "import PackageDescription",
        "",
        f'let package = Package(',
        f'    name: "{package_name}",',
        "    platforms: [",
        *render_package_platforms(),
        "    ],",
        "    products: [",
    ]

    for release in releases:
        product_targets = ", ".join(f'"{target_name}"' for target_name in product_targets_for_release(release))
        lines.append(
            f'        .library(name: "{release.variant.product_name}", targets: [{product_targets}]),'
        )

    lines.extend(
        [
            "    ],",
        ]
    )

    if swiftpm_dependencies:
        lines.extend(
            [
                "    dependencies: [",
                *(
                    f'        .package(url: "{dependency.url}", exact: "{dependency.exact_version}"),'
                    for dependency in swiftpm_dependencies
                ),
                "    ],",
            ]
        )

    lines.extend(
        [
            "    targets: [",
        ]
    )

    for binary_target in binary_target_lines:
        lines.extend(binary_target)

    for support_target in runtime_support_targets:
        dependency_lines = [
            f"                {_render_product_dependency(dependency)},"
            for dependency in support_target.product_dependencies
        ]
        lines.extend(
            [
                "        .target(",
                f'            name: "{support_target.target_name}",',
                "            dependencies: [",
                *dependency_lines,
                "            ],",
                f'            path: "{support_target.path}"',
                "        ),",
            ]
        )

    lines.extend(
        [
            "    ]",
            ")",
            "",
        ]
    )
    return "\n".join(lines)


def render_package_swift(package_name: str, owner: str, repo: str, releases: list[ReleaseAsset]) -> str:
    return _render_package_manifest(
        package_name=package_name,
        releases=releases,
        binary_target_lines=[
            [
                "        .binaryTarget(",
                f'            name: "{release.variant.target_name}",',
                f'            url: "{release_url(owner, repo, release.package_tag, release.variant, release.upstream_tag)}",',
                f'            checksum: "{release.checksum}"',
                "        ),",
            ]
            for release in releases
        ],
    )


def render_local_package_swift(package_name: str, releases: list[ReleaseAsset]) -> str:
    return _render_package_manifest(
        package_name=package_name,
        releases=releases,
        binary_target_lines=[
            [
                "        .binaryTarget(",
                f'            name: "{release.variant.target_name}",',
                f'            path: "Artifacts/{release.variant.target_name}.xcframework"',
                "        ),",
            ]
            for release in releases
        ],
    )


def build_artifact_metadata_payload(release: ReleaseAsset, artifact_path: str) -> dict[str, object]:
    if not artifact_path:
        raise ValueError("artifact_path is required for build artifact metadata")

    return {
        "schema_version": BUILD_ARTIFACT_METADATA_SCHEMA_VERSION,
        "target_name": release.variant.target_name,
        "product_name": release.variant.product_name,
        "module_name": release.variant.module_name,
        "upstream_tag": release.upstream_tag,
        "package_tag": release.package_tag,
        "asset_name": asset_name_for_variant(release.variant, release.upstream_tag),
        "artifact_path": artifact_path,
        "checksum": release.checksum,
        "platforms": [platform.swiftpm_platform for platform in release.variant.platforms],
        "runtime_dependency_model": release.variant.runtime_dependency_model,
        "runtime_dependency_supplier": release.variant.runtime_dependency_supplier,
        "runtime_dependencies": required_dependencies_for_variant(release.variant),
        "strong_runtime_dependencies": required_strong_dependencies_for_variant(release.variant),
        "weak_runtime_dependencies": required_weak_dependencies_for_variant(release.variant),
        "forbidden_runtime_dependencies": forbidden_dependencies_for_variant(release.variant),
    }


def _require_string_field(payload: dict[str, object], field_name: str, source_path: Path) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid {field_name} in {source_path}")
    return value


def _require_string_list_field(payload: dict[str, object], field_name: str, source_path: Path) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"invalid {field_name} in {source_path}")
    return value


def _require_optional_string_list_field(payload: dict[str, object], field_name: str, source_path: Path) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"invalid {field_name} in {source_path}")
    return value


def load_build_artifact_metadata(path: Path) -> BuildArtifactMetadata:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"invalid build artifact metadata in {path}")

    schema_version = payload.get("schema_version")
    if schema_version != BUILD_ARTIFACT_METADATA_SCHEMA_VERSION:
        raise ValueError(f"unsupported build artifact metadata schema in {path}: {schema_version!r}")

    target_name = _require_string_field(payload, "target_name", path)
    variant = variant_for_target_name(target_name)
    upstream_tag = _require_string_field(payload, "upstream_tag", path)
    package_tag = _require_string_field(payload, "package_tag", path)
    checksum = _require_string_field(payload, "checksum", path)
    artifact_path = _require_string_field(payload, "artifact_path", path)

    expected_fields = {
        "product_name": variant.product_name,
        "module_name": variant.module_name,
        "asset_name": asset_name_for_variant(variant, upstream_tag),
    }
    for field_name, expected_value in expected_fields.items():
        actual_value = _require_string_field(payload, field_name, path)
        if actual_value != expected_value:
            raise ValueError(
                f"invalid {field_name} in {path}: expected {expected_value!r}, found {actual_value!r}"
            )

    actual_platforms = _require_string_list_field(payload, "platforms", path)
    expected_platforms = [platform.swiftpm_platform for platform in variant.platforms]
    if actual_platforms != expected_platforms:
        raise ValueError(
            f"invalid platforms in {path}: expected {expected_platforms!r}, found {actual_platforms!r}"
        )

    actual_runtime_dependency_model = _require_string_field(payload, "runtime_dependency_model", path)
    if actual_runtime_dependency_model != variant.runtime_dependency_model:
        raise ValueError(
            f"invalid runtime_dependency_model in {path}: "
            f"expected {variant.runtime_dependency_model!r}, found {actual_runtime_dependency_model!r}"
        )
    actual_runtime_dependency_supplier = _require_string_field(payload, "runtime_dependency_supplier", path)
    if actual_runtime_dependency_supplier != variant.runtime_dependency_supplier:
        raise ValueError(
            f"invalid runtime_dependency_supplier in {path}: "
            f"expected {variant.runtime_dependency_supplier!r}, found {actual_runtime_dependency_supplier!r}"
        )
    actual_runtime_dependencies = _require_optional_string_list_field(payload, "runtime_dependencies", path)
    expected_runtime_dependencies = required_dependencies_for_variant(variant)
    if actual_runtime_dependencies != expected_runtime_dependencies:
        raise ValueError(
            f"invalid runtime_dependencies in {path}: "
            f"expected {expected_runtime_dependencies!r}, found {actual_runtime_dependencies!r}"
        )
    actual_strong_runtime_dependencies = _require_optional_string_list_field(payload, "strong_runtime_dependencies", path)
    expected_strong_runtime_dependencies = required_strong_dependencies_for_variant(variant)
    if actual_strong_runtime_dependencies != expected_strong_runtime_dependencies:
        raise ValueError(
            f"invalid strong_runtime_dependencies in {path}: "
            f"expected {expected_strong_runtime_dependencies!r}, found {actual_strong_runtime_dependencies!r}"
        )
    actual_weak_runtime_dependencies = _require_optional_string_list_field(payload, "weak_runtime_dependencies", path)
    expected_weak_runtime_dependencies = required_weak_dependencies_for_variant(variant)
    if actual_weak_runtime_dependencies != expected_weak_runtime_dependencies:
        raise ValueError(
            f"invalid weak_runtime_dependencies in {path}: "
            f"expected {expected_weak_runtime_dependencies!r}, found {actual_weak_runtime_dependencies!r}"
        )
    actual_forbidden_runtime_dependencies = _require_optional_string_list_field(payload, "forbidden_runtime_dependencies", path)
    expected_forbidden_runtime_dependencies = forbidden_dependencies_for_variant(variant)
    if actual_forbidden_runtime_dependencies != expected_forbidden_runtime_dependencies:
        raise ValueError(
            f"invalid forbidden_runtime_dependencies in {path}: "
            f"expected {expected_forbidden_runtime_dependencies!r}, found {actual_forbidden_runtime_dependencies!r}"
        )

    return BuildArtifactMetadata(
        release_asset=ReleaseAsset(
            variant=variant,
            upstream_tag=upstream_tag,
            package_tag=package_tag,
            checksum=checksum,
        ),
        artifact_path=artifact_path,
    )
