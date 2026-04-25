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
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.9/ncnn-20260113-apple.xcframework.zip",
            checksum: "7da27da756d3af8103e3afe4bfc87ed705cbfb6cf40d9e39be1e2963b034d636"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260113-alpha.9/ncnn-20260113-apple-vulkan.xcframework.zip",
            checksum: "77a6794fdbb31dc228a58378fe2b86a52f0830b97614bf97514153f43fcdb20b"
        ),
    ]
)
