from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
PUBLISH_CORE_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "_publish-upstream-release-core.yml"
SYNC_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "publish-latest-upstream-alpha.yml"
BACKFILL_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "publish-upstream-release-manually.yml"
VALIDATE_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "validate-apple-release-pipeline.yml"
PACKAGE_DOC_PATH = REPO_ROOT / "docs" / "how-to-build" / "swiftpm-binary-package.md"
README_PATH = REPO_ROOT / "README.md"


class ReleaseBranchWorkflowTests(unittest.TestCase):
    def _job_section(self, workflow: str, job_name: str, next_job_name: str | None = None) -> str:
        start_marker = f"  {job_name}:\n"
        start_index = workflow.index(start_marker)
        if next_job_name is None:
            return workflow[start_index:]
        end_marker = f"  {next_job_name}:\n"
        end_index = workflow.index(end_marker, start_index + len(start_marker))
        return workflow[start_index:end_index]

    def test_repo_keeps_only_packaging_specific_workflows(self) -> None:
        workflow_names = sorted(path.name for path in WORKFLOWS_DIR.glob("*.yml"))
        self.assertEqual(
            workflow_names,
            [
                "_publish-upstream-release-core.yml",
                "publish-latest-upstream-alpha.yml",
                "publish-upstream-release-manually.yml",
                "validate-apple-release-pipeline.yml",
            ],
        )

    def test_sync_workflow_delegates_to_shared_publish_core(self) -> None:
        workflow = SYNC_WORKFLOW_PATH.read_text()
        self.assertIn("name: publish-latest-upstream-alpha", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertIn("uses: ./.github/workflows/_publish-upstream-release-core.yml", workflow)
        self.assertIn("release_channel: sync", workflow)
        self.assertNotIn("gh release create", workflow)

    def test_backfill_workflow_delegates_to_shared_publish_core(self) -> None:
        workflow = BACKFILL_WORKFLOW_PATH.read_text()
        self.assertIn("name: publish-upstream-release-manually", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertIn("uses: ./.github/workflows/_publish-upstream-release-core.yml", workflow)
        self.assertIn('upstream_tag: ${{ inputs.upstream_tag }}', workflow)
        self.assertIn('release_channel: ${{ inputs.release_channel }}', workflow)
        self.assertNotIn("gh release create", workflow)

    def test_publish_core_workflow_owns_release_steps(self) -> None:
        workflow = PUBLISH_CORE_WORKFLOW_PATH.read_text()
        self.assertIn("on:", workflow)
        self.assertIn("workflow_call:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("release_channel:", workflow)
        self.assertIn("scripts/spm/source_acquisition.py fetch-tags", workflow)
        self.assertIn("scripts/spm/release_state.py", workflow)
        self.assertIn("inspect-release", workflow)
        self.assertIn("scripts/spm/source_acquisition.py export-source", workflow)
        self.assertIn("--output Package.swift", workflow)
        self.assertIn('--package-tag "${{ needs.resolve.outputs.package_tag }}"', workflow)
        self.assertIn("git add Package.swift", workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn("gh release upload", workflow)
        self.assertIn("gh api --method PATCH", workflow)
        self.assertIn('TARGET_BRANCH="${{ github.event.repository.default_branch || \'main\' }}"', workflow)
        self.assertNotIn("DEVELOPER_DIR:", workflow)

    def test_package_doc_describes_main_release_branch_model(self) -> None:
        document = PACKAGE_DOC_PATH.read_text()
        self.assertIn("main` branch", document)
        self.assertIn("independent wrapper repo", document)
        self.assertIn("`X.Y.Z-alpha.N`", document)
        self.assertIn("`alpha` or `stable`", document)
        self.assertIn("repo-local source acquisition contract", document)
        self.assertIn("preflight_apple_platforms.py", document)
        self.assertIn("validate_package_contract.py", document)
        self.assertIn("ccache", document)
        self.assertNotIn("synchwithupstream", document)
        self.assertNotIn("local-debug convenience", document)

    def test_publish_core_runs_packaging_verification_gates(self) -> None:
        workflow = PUBLISH_CORE_WORKFLOW_PATH.read_text()
        build_job = self._job_section(workflow, "build", "release")
        self.assertIn("python3 -m unittest", workflow)
        self.assertIn("scripts.spm.tests.test_xcframework_validation", workflow)
        self.assertIn("scripts/spm/preflight_apple_platforms.py", workflow)
        self.assertIn("scripts/spm/validate_mergeable_xcframework.py", workflow)
        self.assertIn("if [ \"${{ inputs.release_channel }}\" = \"alpha\" ]", workflow)
        self.assertIn("runs-on: macos-15", build_job)
        self.assertNotIn("runs-on: macos-15-intel", build_job)
        self.assertIn("HOMEBREW_CACHE: ${{ github.workspace }}/.homebrew-cache", build_job)
        self.assertIn("restore-homebrew-download-cache", build_job)
        self.assertIn("uses: actions/cache@v5", build_job)
        self.assertIn("path: ${{ github.workspace }}/.ccache", build_job)
        self.assertIn("CCACHE_DIR: ${{ github.workspace }}/.ccache", build_job)
        self.assertIn("resolve-xcode-version", build_job)
        self.assertIn("preflight-apple-platforms", build_job)
        self.assertIn("ccache-v3", build_job)
        self.assertIn("steps.xcode.outputs.version_key", build_job)
        self.assertIn("hashFiles(", build_job)
        self.assertIn("scripts/spm/build_apple_xcframework.py", build_job)
        self.assertIn("scripts/spm/archive_builder.py", build_job)
        self.assertIn("scripts/spm/packaging.py", build_job)
        self.assertIn("scripts/spm/platforms.json", build_job)
        self.assertIn("toolchains/ios.toolchain.cmake", build_job)
        self.assertIn("${{ runner.temp }}/spm-artifacts/${{ matrix.variant }}/*.xcframework.zip", build_job)
        self.assertIn(
            "${{ runner.temp }}/spm-artifacts/${{ matrix.variant }}/${{ matrix.variant }}.release.json",
            build_job,
        )
        self.assertIn("overwrite: true", build_job)
        self.assertIn("build-ccache-stats", build_job)
        self.assertIn("--release-archive artifacts/ncnn/ncnn-*.xcframework.zip", workflow)
        self.assertIn("--release-archive artifacts/ncnn_vulkan/ncnn-*.xcframework.zip", workflow)

    def test_validate_workflow_runs_on_push_and_pull_request(self) -> None:
        workflow = VALIDATE_WORKFLOW_PATH.read_text()
        build_job = self._job_section(workflow, "build", "package_contract")
        package_contract_job = self._job_section(workflow, "package_contract")
        self.assertIn("name: validate-apple-release-pipeline", workflow)
        self.assertIn("push:", workflow)
        self.assertIn("- main", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("upstream_tag:", workflow)
        self.assertIn("scripts.spm.tests.test_release_flow", workflow)
        self.assertIn("scripts.spm.tests.test_release_state", workflow)
        self.assertIn("scripts/spm/preflight_apple_platforms.py", workflow)
        self.assertIn("scripts/spm/validate_package_contract.py", workflow)
        self.assertIn("scripts/spm/validate_mergeable_xcframework.py", workflow)
        self.assertIn("scripts/spm/source_acquisition.py fetch-tags", workflow)
        self.assertIn("--explicit-tag \"${{ inputs.upstream_tag }}\"", workflow)
        self.assertIn("package_tag: ${{ steps.resolve.outputs.package_tag }}", workflow)
        self.assertIn('--package-tag "${{ needs.verify.outputs.package_tag }}"', workflow)
        self.assertIn("runs-on: macos-15", build_job)
        self.assertNotIn("runs-on: macos-15-intel", build_job)
        self.assertIn("HOMEBREW_CACHE: ${{ github.workspace }}/.homebrew-cache", build_job)
        self.assertIn("restore-homebrew-download-cache", build_job)
        self.assertIn("uses: actions/cache@v5", build_job)
        self.assertIn("path: ${{ github.workspace }}/.ccache", build_job)
        self.assertIn("CCACHE_DIR: ${{ github.workspace }}/.ccache", build_job)
        self.assertIn("resolve-xcode-version", build_job)
        self.assertIn("preflight-apple-platforms", build_job)
        self.assertIn("ccache-v3", build_job)
        self.assertIn("steps.xcode.outputs.version_key", build_job)
        self.assertIn("hashFiles(", build_job)
        self.assertIn("scripts/spm/build_apple_xcframework.py", build_job)
        self.assertIn("scripts/spm/archive_builder.py", build_job)
        self.assertIn("scripts/spm/packaging.py", build_job)
        self.assertIn("scripts/spm/platforms.json", build_job)
        self.assertIn("toolchains/ios.toolchain.cmake", build_job)
        self.assertIn("${{ runner.temp }}/spm-artifacts/${{ matrix.variant }}/*.xcframework.zip", build_job)
        self.assertIn(
            "${{ runner.temp }}/spm-artifacts/${{ matrix.variant }}/${{ matrix.variant }}.release.json",
            build_job,
        )
        self.assertIn("actions/upload-artifact@v7", build_job)
        self.assertIn("overwrite: true", build_job)
        self.assertIn("build-ccache-stats", build_job)
        self.assertIn("Validate generated package contract", package_contract_job)
        self.assertIn("actions/download-artifact@v8", package_contract_job)
        self.assertIn("validate-generated-package-contract", package_contract_job)
        self.assertIn("--release-archive artifacts/ncnn/ncnn-*.xcframework.zip", package_contract_job)
        self.assertIn("--release-archive artifacts/ncnn_vulkan/ncnn-*.xcframework.zip", package_contract_job)
        self.assertNotIn("DEVELOPER_DIR:", workflow)

    def test_readme_describes_wrapper_repo_only(self) -> None:
        readme = README_PATH.read_text()
        self.assertIn("wrapper repository", readme)
        self.assertIn("GitHub Release", readme)
        self.assertIn("Tencent/ncnn", readme)
        self.assertNotIn("build for android", readme.lower())
        self.assertNotIn("qq", readme.lower())


if __name__ == "__main__":
    unittest.main()
