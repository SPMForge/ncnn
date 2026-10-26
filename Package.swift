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
        .package(url: "https://github.com/SPMForge/MoltenVK.git", exact: "1.4.2-alpha.2"),
    ],
    targets: [
        .binaryTarget(
            name: "ncnn",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20261020-alpha.2/ncnn-20261020-apple.xcframework.zip",
            checksum: "1772ba606ce4cb0fd11b2d95dea228f7fc820906d746c0d3fb15ac3bdbe9f7ab"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20261020-alpha.2/ncnn-20261020-apple-vulkan.xcframework.zip",
            checksum: "2cf30c0e95c87fb6a4ddcf1b679ad1d27d3881806be11e32189d4c630c24b867"
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
