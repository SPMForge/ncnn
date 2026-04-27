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
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.11/ncnn-20260113-apple.xcframework.zip",
            checksum: "7ba3aabd3d99aa0d2355829f74df52c1c8cc5af63908060c11c45b8bb6347765"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.11/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "15b2aef11162e4376c5c54d6e2f69b302b33ed81f661de7584867eb3742cb05a"
        ),
    ]
)
