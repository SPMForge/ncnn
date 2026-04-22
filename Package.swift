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
            checksum: "4b00d79aae495bf71e3580605e82b31d4869b7770b74b5562d662dc8cb6a2875"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.1/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "77736e5e680ea3e1fcda9e7e96ace2152b74c3b9d0165d6740d70832595d0eb7"
        ),
    ]
)
