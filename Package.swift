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
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.12/ncnn-20260113-apple.xcframework.zip",
            checksum: "d3a74a9f0409765b175105019d3e6ecad4b62287d0ff27de5e82d1f34b12b5bf"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.12/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "8b53ec7846e330caaafec55b60d6d3397178264d1b7c41cace088052423530a6"
        ),
    ]
)
