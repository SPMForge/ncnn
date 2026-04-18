// swift-tools-version: 5.9

import Foundation
import PackageDescription

let currentReleaseMetadataURL = URL(fileURLWithPath: #filePath)
    .deletingLastPathComponent()
    .appendingPathComponent("scripts/spm/current_release.json")

let package = Package(
    name: "ncnn",
    platforms: [
        .iOS(.v13),
        .macOS(.v11),
        .macCatalyst(.v13),
        .tvOS(.v11),
        .watchOS(.v6),
        .visionOS(.v1),
    ],
    products: releaseProducts(),
    targets: releaseTargets()
)

private func loadReleaseMetadata() -> [[String: Any]] {
    guard
        let data = try? Data(contentsOf: currentReleaseMetadataURL),
        let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
        let releases = object["releases"] as? [[String: Any]]
    else {
        return []
    }

    return releases
}

private func releaseProducts() -> [Product] {
    loadReleaseMetadata().compactMap { release in
        guard
            let productName = release["product_name"] as? String,
            let targetName = release["target_name"] as? String
        else {
            return nil
        }

        return .library(name: productName, targets: [targetName])
    }
}

private func releaseTargets() -> [Target] {
    loadReleaseMetadata().compactMap { release in
        guard
            let targetName = release["target_name"] as? String,
            let urlString = release["url"] as? String,
            let checksum = release["checksum"] as? String
        else {
            return nil
        }

        return .binaryTarget(name: targetName, url: urlString, checksum: checksum)
    }
}
