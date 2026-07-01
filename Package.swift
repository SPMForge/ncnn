// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "ncnn",
    platforms: [
        .iOS("14.0"),
        .macOS("11.0"),
        .macCatalyst("13.1"),
        .tvOS("14.0"),
        .watchOS("6.0"),
        .visionOS("1.0"),
    ],
    products: [
        .library(name: "NCNN", targets: ["ncnn"]),
        .library(name: "NCNNVulkan", targets: ["ncnn_vulkan", "ncnn_vulkan_runtime_support"]),
    ],
    dependencies: [
        .package(url: "https://github.com/SPMForge/MoltenVK.git", exact: "1.4.1-alpha.7"),
    ],
    targets: [
        .binaryTarget(
            name: "ncnn",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260526-alpha.35/ncnn-20260526-apple.xcframework.zip",
            checksum: "fb237dac67df8ddbc0177f4f78dbed979e62dfe7d0862a484ddb1120e04baf9c"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260526-alpha.35/ncnn-20260526-apple-vulkan.xcframework.zip",
            checksum: "b80e4962a77c84557c0f6322e539340016de5f1c9107f104a9d38dde0fe2734f"
        ),
        .target(
            name: "ncnn_vulkan_runtime_support",
            dependencies: [
                .product(name: "MoltenVK", package: "MoltenVK"),
            ],
            path: "Sources/ncnn_vulkan_runtime_support"
        ),
    ]
)
