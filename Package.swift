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
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.7/ncnn-20260113-apple.xcframework.zip",
            checksum: "904ef2eb8b2e11b4a5e083aac8fea734991571a5ef7dc0fc69374a003d92470e"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.7/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "be7a27e291f1285111cd3548b15f32d311df0c434f9347bfee2f3c8fe7873844"
        ),
    ]
)
