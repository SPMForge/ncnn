from __future__ import annotations

from dataclasses import dataclass
import json
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


@dataclass(frozen=True)
class ReleaseAsset:
    variant: Variant
    upstream_tag: str
    package_tag: str
    checksum: str


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
PACKAGE_SWIFT_PATH = REPO_ROOT / "Package.swift"
BUILD_ARTIFACT_METADATA_SCHEMA_VERSION = 1
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
        Platform("Mac Catalyst", "ios-maccatalyst", "MAC_CATALYST", "generic/platform=macOS,variant=Mac Catalyst", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["ios-maccatalyst"]),
        Platform("tvOS", "tvos", "TVOS", "generic/platform=tvOS", ("arm64",), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["tvos"]),
        Platform("tvOS Simulator", "tvos-simulator", "SIMULATORARM64_TVOS", "generic/platform=tvOS Simulator", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["tvos"]),
        Platform("visionOS", "xros", "VISIONOS", "generic/platform=visionOS", ("arm64",), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["xros"]),
        Platform("visionOS Simulator", "xros-simulator", "SIMULATOR_VISIONOS", "generic/platform=visionOS Simulator", ("arm64", "x86_64"), PACKAGE_PLATFORM_DEPLOYMENT_TARGETS["xros"]),
    ),
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


def render_package_platforms() -> list[str]:
    return [
        f'        .{PACKAGE_PLATFORM_FUNCTIONS[platform_key]}("{PACKAGE_PLATFORM_DEPLOYMENT_TARGETS[platform_key]}"),'
        for platform_key in PACKAGE_PLATFORM_ORDER
    ]


def render_package_swift(package_name: str, owner: str, repo: str, releases: list[ReleaseAsset]) -> str:
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
        lines.append(
            f'        .library(name: "{release.variant.product_name}", targets: ["{release.variant.target_name}"]),'
        )

    lines.extend(
        [
            "    ],",
            "    targets: [",
        ]
    )

    for release in releases:
        lines.extend(
            [
                "        .binaryTarget(",
                f'            name: "{release.variant.target_name}",',
                f'            url: "{release_url(owner, repo, release.package_tag, release.variant, release.upstream_tag)}",',
                f'            checksum: "{release.checksum}"',
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

    return BuildArtifactMetadata(
        release_asset=ReleaseAsset(
            variant=variant,
            upstream_tag=upstream_tag,
            package_tag=package_tag,
            checksum=checksum,
        ),
        artifact_path=artifact_path,
    )
