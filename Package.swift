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
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260526-alpha.14/ncnn-20260526-apple.xcframework.zip",
            checksum: "cabfe494ba86ee5e11b863edec3cf8a860275a9f9648ec4a871fa893da7210a4"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260526-alpha.14/ncnn-20260526-apple-vulkan.xcframework.zip",
            checksum: "fbfe847f10165ed144bcc1eb66f539ff60d62149881ee9177050f0c71ace88a6"
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
