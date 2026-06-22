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
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260526-alpha.26/ncnn-20260526-apple.xcframework.zip",
            checksum: "add4bb5221ebdbfd4d9a2577440c5dc790eef414ac7b4ba0a990d3e334349f00"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260526-alpha.26/ncnn-20260526-apple-vulkan.xcframework.zip",
            checksum: "f736ea45a1dc5c44cab0bc6affa8f50c8d2650ef43e405004a95efa56ecedc70"
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
