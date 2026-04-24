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
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.8/ncnn-20260113-apple.xcframework.zip",
            checksum: "fab1e089ce98616c7c021ed880dbab0d52868f2c0298582a5d3422f82c868478"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.8/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "6d7e0f17377696452d6b1e270cca7bd6a65b8a60f2756d6614db89818cdd0e48"
        ),
    ]
)
