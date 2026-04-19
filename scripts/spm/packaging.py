from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


_UPSTREAM_TAG_PATTERN = re.compile(r"^\d{8}$")


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


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = Path(__file__).resolve().parent
DEFAULT_PACKAGE_NAME = "ncnn"
DEFAULT_OWNER = "SPMForge"
DEFAULT_REPO = "ncnn"
TOOLCHAIN_FILE = REPO_ROOT / "toolchains" / "ios.toolchain.cmake"
CURRENT_RELEASE_METADATA_PATH = SCRIPTS_ROOT / "current_release.json"
PACKAGE_SWIFT_PATH = REPO_ROOT / "Package.swift"

CPU_VARIANT = Variant(
    target_name="ncnn",
    product_name="NCNN",
    asset_suffix="apple",
    module_name="ncnn",
    platforms=(
        Platform("iOS", "ios", "OS64", "generic/platform=iOS", ("arm64",), "13.0"),
        Platform("iOS Simulator", "ios-simulator", "SIMULATORARM64", "generic/platform=iOS Simulator", ("arm64", "x86_64"), "13.0"),
        Platform("macOS", "macos", "MAC", "generic/platform=macOS", ("arm64", "x86_64"), "11.0"),
        Platform("Mac Catalyst", "ios-maccatalyst", "MAC_CATALYST", "generic/platform=macOS,variant=Mac Catalyst", ("arm64", "x86_64"), "13.1"),
        Platform("tvOS", "tvos", "TVOS", "generic/platform=tvOS", ("arm64",), "11.0"),
        Platform("tvOS Simulator", "tvos-simulator", "SIMULATORARM64_TVOS", "generic/platform=tvOS Simulator", ("arm64", "x86_64"), "11.0"),
        Platform("watchOS", "watchos", "WATCHOS", "generic/platform=watchOS", ("arm64", "arm64_32"), "6.0"),
        Platform("watchOS Simulator", "watchos-simulator", "SIMULATOR_WATCHOS", "generic/platform=watchOS Simulator", ("arm64", "x86_64"), "6.0"),
        Platform("visionOS", "xros", "VISIONOS", "generic/platform=visionOS", ("arm64",), "1.0"),
        Platform("visionOS Simulator", "xros-simulator", "SIMULATOR_VISIONOS", "generic/platform=visionOS Simulator", ("arm64", "x86_64"), "1.0"),
    ),
)

VULKAN_VARIANT = Variant(
    target_name="ncnn_vulkan",
    product_name="NCNNVulkan",
    asset_suffix="apple-vulkan",
    module_name="ncnn_vulkan",
    platforms=(
        Platform("iOS", "ios", "OS64", "generic/platform=iOS", ("arm64",), "13.0"),
        Platform("iOS Simulator", "ios-simulator", "SIMULATORARM64", "generic/platform=iOS Simulator", ("arm64", "x86_64"), "13.0"),
        Platform("macOS", "macos", "MAC", "generic/platform=macOS", ("arm64", "x86_64"), "11.0"),
        Platform("Mac Catalyst", "ios-maccatalyst", "MAC_CATALYST", "generic/platform=macOS,variant=Mac Catalyst", ("arm64", "x86_64"), "13.1"),
        Platform("tvOS", "tvos", "TVOS", "generic/platform=tvOS", ("arm64",), "11.0"),
        Platform("tvOS Simulator", "tvos-simulator", "SIMULATORARM64_TVOS", "generic/platform=tvOS Simulator", ("arm64", "x86_64"), "11.0"),
        Platform("visionOS", "xros", "VISIONOS", "generic/platform=visionOS", ("arm64",), "1.0"),
        Platform("visionOS Simulator", "xros-simulator", "SIMULATOR_VISIONOS", "generic/platform=visionOS Simulator", ("arm64", "x86_64"), "1.0"),
    ),
)

VARIANTS = (CPU_VARIANT, VULKAN_VARIANT)
VARIANTS_BY_TARGET = {variant.target_name: variant for variant in VARIANTS}


def package_tag_for_upstream_tag(upstream_tag: str) -> str:
    if not _UPSTREAM_TAG_PATTERN.match(upstream_tag):
        raise ValueError(f"unsupported upstream tag format: {upstream_tag}")
    return f"1.0.{upstream_tag}"


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


def render_package_swift(package_name: str, owner: str, repo: str, releases: list[ReleaseAsset]) -> str:
    lines = [
        "// swift-tools-version: 5.9",
        "",
        "import PackageDescription",
        "",
        f'let package = Package(',
        f'    name: "{package_name}",',
        "    platforms: [",
        "        .iOS(.v13),",
        "        .macOS(.v11),",
        "        .macCatalyst(.v13),",
        "        .tvOS(.v11),",
        "        .watchOS(.v6),",
        "        .visionOS(.v1),",
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
        lines.append(
            f'        .binaryTarget(name: "{release.variant.target_name}", url: "{release_url(owner, repo, release.package_tag, release.variant, release.upstream_tag)}", checksum: "{release.checksum}"),'
        )

    lines.extend(
        [
            "    ]",
            ")",
            "",
        ]
    )
    return "\n".join(lines)
