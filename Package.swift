// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "ncnn",
    platforms: [
        .iOS("14.0"),
        .macOS("11.0"),
        .macCatalyst("13.1"),
        .tvOS("14.0"),
        .watchOS("6.0"),
        .visionOS("1.0"),
    ],
    products: [
        .library(name: "NCNN", targets: ["ncnn"]),
        .library(name: "NCNNVulkan", targets: ["ncnn_vulkan", "ncnn_vulkan_runtime_support"]),
    ],
    dependencies: [
        .package(url: "https://github.com/SPMForge/MoltenVK.git", exact: "1.4.1-alpha.7"),
    ],
    targets: [
        .binaryTarget(
            name: "ncnn",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260526-alpha.89/ncnn-20260526-apple.xcframework.zip",
            checksum: "6a26cf8cea9f7b45a8c041cd767341e5acb06151ed94012342d5443c8ad5637c"
        ),
        .binaryTarget(
            name: "ncnn_vulkan",
            url: "https://github.com/SPMForge/ncnn/releases/download/1.0.20260526-alpha.89/ncnn-20260526-apple-vulkan.xcframework.zip",
            checksum: "10eb077ce756ce51d8fa404086d659b8672f27c901bd1aaf2e57f8197954b61d"
        ),
        .target(
            name: "ncnn_vulkan_runtime_support",
            dependencies: [
                .product(name: "MoltenVK", package: "MoltenVK"),
            ],
            path: "Sources/ncnn_vulkan_runtime_support"
        ),
    ]
)
