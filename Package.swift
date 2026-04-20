// swift-tools-version: 5.9

import Foundation
import PackageDescription

let currentReleaseMetadataURL = URL(fileURLWithPath: #filePath)
    .deletingLastPathComponent()
    .appendingPathComponent("scripts/spm/current_release.json")
let platformMetadataURL = URL(fileURLWithPath: #filePath)
    .deletingLastPathComponent()
    .appendingPathComponent("scripts/spm/platforms.json")
let releaseMetadata = loadReleaseMetadata()
let packagePlatformVersions = loadPackagePlatformVersions()

let package = Package(
    name: "ncnn",
    platforms: releasePlatforms(),
    products: releaseProducts(),
    targets: releaseTargets()
)

private func loadJSONObject(at url: URL, description: String) -> [String: Any] {
    guard
        let data = try? Data(contentsOf: url),
        let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    else {
        fatalError("Failed to load \(description) from \(url.path).")
    }

    return object
}

private func loadReleaseMetadata() -> [[String: Any]] {
    let object = loadJSONObject(at: currentReleaseMetadataURL, description: "release metadata")
    guard let releases = object["releases"] as? [[String: Any]] else {
        fatalError("Invalid release metadata at \(currentReleaseMetadataURL.path): missing 'releases' array.")
    }

    return releases
}

private func loadPackagePlatformVersions() -> [String: String] {
    let object = loadJSONObject(at: platformMetadataURL, description: "platform metadata")
    guard let platforms = object["package_platforms"] as? [String: String] else {
        fatalError("Invalid platform metadata at \(platformMetadataURL.path): missing 'package_platforms' map.")
    }

    return platforms
}

private func requiredString(_ key: String, in release: [String: Any], index: Int) -> String {
    guard let value = release[key] as? String, !value.isEmpty else {
        fatalError("Invalid release metadata at \(currentReleaseMetadataURL.path): release[\(index)] missing string '\(key)'.")
    }

    return value
}

private func requiredPlatformVersion(_ key: String) -> String {
    guard let version = packagePlatformVersions[key], !version.isEmpty else {
        fatalError("Invalid platform metadata at \(platformMetadataURL.path): missing version for '\(key)'.")
    }

    return version
}

private func releasePlatforms() -> [SupportedPlatform] {
    [
        .iOS(requiredPlatformVersion("ios")),
        .macOS(requiredPlatformVersion("macos")),
        .macCatalyst(requiredPlatformVersion("ios-maccatalyst")),
        .tvOS(requiredPlatformVersion("tvos")),
        .watchOS(requiredPlatformVersion("watchos")),
        .visionOS(requiredPlatformVersion("xros")),
    ]
}

private func releaseProducts() -> [Product] {
    releaseMetadata.enumerated().map { index, release in
        let productName = requiredString("product_name", in: release, index: index)
        let targetName = requiredString("target_name", in: release, index: index)
        return .library(name: productName, targets: [targetName])
    }
}

private func releaseTargets() -> [Target] {
    releaseMetadata.enumerated().map { index, release in
        let targetName = requiredString("target_name", in: release, index: index)
        let urlString = requiredString("url", in: release, index: index)
        let checksum = requiredString("checksum", in: release, index: index)
        return .binaryTarget(name: targetName, url: urlString, checksum: checksum)
    }
}
