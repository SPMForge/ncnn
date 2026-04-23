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
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.5/ncnn-20260113-apple.xcframework.zip",
            checksum: "1ee69cb9e83b59fe69afe374becd0d2b94292edbc1eff9d91cb7a5cf5f84ef6a"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.5/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "c427c1f8e5979e429203d09cecd5c83fe2538693744ab4ca297a81d7debde213"
        ),
    ]
)
