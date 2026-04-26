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
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.10/ncnn-20260113-apple.xcframework.zip",
            checksum: "f47d02c5b0cebc996a9b53fc823369a34369ccd864e0cb5d6d73fccf011d8759"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.10/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "83281dd8d9fcacb1bf117bfbc8a2ab1fa0c9899d2bad94316593af7b03ca29d5"
        ),
    ]
)
