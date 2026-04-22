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
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.1/ncnn-20260113-apple.xcframework.zip",
            checksum: "579d9437e2d8995ab0907c44413b74e60b6599cdfcf6e741dd8ed03095fac6ae"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.1/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "0894e63dd52b7d5f48eeed233a7922aaf7e57d9b9c9ed2d2353e8be49b705a40"
        ),
    ]
)
