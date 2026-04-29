// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "ncnn",
    platforms: [
        .iOS("13.0"),
        .macOS("11.0"),
        .macCatalyst("13.1"),
        .tvOS("11.0"),
        .watchOS("6.0"),
        .visionOS("1.0"),
    ],
    products: [
        .library(name: "NCNN", targets: ["ncnn"]),
        .library(name: "NCNNVulkan", targets: ["ncnn_vulkan", "ncnn_vulkan_runtime"]),
    ],
    dependencies: [
        .package(url: "https://github.com/SPMForge/MoltenVK.git", exact: "1.4.1-alpha.6"),
    ],
    targets: [
        .binaryTarget(
            name: "ncnn",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.13/ncnn-20260113-apple.xcframework.zip",
            checksum: "6fbebf4240bd6481afe2672c3b8f662c5b4668e97ccd728975eb8c0ea1e4da7b"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.13/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "7c370a4b27faad7bb07debe42fd8986bdff273619a01c10823331c3d1c9f9503"
        ),
        .target(
            name: "ncnn_vulkan_runtime",
            dependencies: [
                .product(name: "MoltenVK", package: "MoltenVK"),
            ],
            path: "Sources/ncnn_vulkan_runtime"
        ),
    ]
)
