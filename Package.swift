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
        .library(name: "NCNNVulkan", targets: ["ncnn_vulkan"]),
    ],
    targets: [
        .binaryTarget(
            name: "ncnn",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.6/ncnn-20260113-apple.xcframework.zip",
            checksum: "8b213779d34cb6f14a08646ed912f7ee1084ba22f85a16a7f2f9cd24b667020f"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.6/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "39dfae7be537fe3a9a1628d3d45263d13968d62e78b5c797408ec7c73628ff15"
        ),
    ]
)
