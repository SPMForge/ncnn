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
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.4/ncnn-20260113-apple.xcframework.zip",
            checksum: "97778a13eaf6bebdbc45cc4440d13d7781175377f891d40a9ce8c5d7ba9ee572"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.4/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "fb3f47ee6f94725a1d5862d1b41f83556b050b875dcfde101d5b99bff588df36"
        ),
    ]
)
