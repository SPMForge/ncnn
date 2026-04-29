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
        .package(url: "https://github.com/SPMForge/MoltenVK.git", exact: "1.4.1-alpha.7"),
    ],
    targets: [
        .binaryTarget(
            name: "ncnn",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.14/ncnn-20260113-apple.xcframework.zip",
            checksum: "7e617be59dddbbc722485feb2374c3e6096e0a8c88334f82745e102138eb413b"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.14/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "aff6294d76e0f902e767867f99c98e87b06a83715bfd6d86f3e481e29afc45d3"
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
