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
        self.assertIn("uses: ./.github/workflows/_publish-upstream-release-core.yml", workflow)
        self.assertIn("release_channel: sync", workflow)
        self.assertNotIn("gh release create", workflow)

    def test_backfill_workflow_delegates_to_shared_publish_core(self) -> None:
        workflow = BACKFILL_WORKFLOW_PATH.read_text()
        self.assertIn("name: publish-upstream-release-manually", workflow)
        self.assertIn("uses: ./.github/workflows/_publish-upstream-release-core.yml", workflow)
        self.assertIn('upstream_tag: ${{ inputs.upstream_tag }}', workflow)
        self.assertIn('release_channel: ${{ inputs.release_channel }}', workflow)
        self.assertNotIn("gh release create", workflow)

    def test_publish_core_workflow_owns_release_steps(self) -> None:
        workflow = PUBLISH_CORE_WORKFLOW_PATH.read_text()
        self.assertIn("on:", workflow)
        self.assertIn("workflow_call:", workflow)
        self.assertIn("release_channel:", workflow)
        self.assertIn("scripts/spm/source_acquisition.py fetch-tags", workflow)
        self.assertIn("scripts/spm/source_acquisition.py export-source", workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn('TARGET_BRANCH="${{ github.event.repository.default_branch || \'main\' }}"', workflow)

    def test_package_doc_describes_main_release_branch_model(self) -> None:
        document = PACKAGE_DOC_PATH.read_text()
        self.assertIn("main` branch", document)
        self.assertIn("independent wrapper repo", document)
        self.assertIn("`X.Y.Z-alpha.N`", document)
        self.assertIn("`alpha` or `stable`", document)
        self.assertIn("repo-local source acquisition contract", document)
        self.assertNotIn("synchwithupstream", document)
        self.assertNotIn("local-debug convenience", document)

    def test_publish_core_runs_packaging_verification_gates(self) -> None:
        workflow = PUBLISH_CORE_WORKFLOW_PATH.read_text()
        build_job = self._job_section(workflow, "build", "release")
        self.assertIn("python3 -m unittest", workflow)
        self.assertIn("scripts.spm.tests.test_xcframework_validation", workflow)
        self.assertIn("scripts/spm/validate_mergeable_xcframework.py", workflow)
        self.assertIn("if [ \"${{ inputs.release_channel }}\" = \"alpha\" ]", workflow)
        self.assertIn("runs-on: macos-15", build_job)
        self.assertNotIn("runs-on: macos-15-intel", build_job)
        self.assertIn("uses: actions/cache@v4", build_job)
        self.assertIn("path: ${{ github.workspace }}/.ccache", build_job)
        self.assertIn("CCACHE_DIR: ${{ github.workspace }}/.ccache", build_job)
        self.assertIn("build-ccache-stats", build_job)

    def test_validate_workflow_runs_on_push_and_pull_request(self) -> None:
        workflow = VALIDATE_WORKFLOW_PATH.read_text()
        build_job = self._job_section(workflow, "build")
        self.assertIn("name: validate-apple-release-pipeline", workflow)
        self.assertIn("push:", workflow)
        self.assertIn("- main", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("upstream_tag:", workflow)
        self.assertIn("scripts.spm.tests.test_release_flow", workflow)
        self.assertIn("scripts/spm/validate_mergeable_xcframework.py", workflow)
        self.assertIn("scripts/spm/source_acquisition.py fetch-tags", workflow)
        self.assertIn("--explicit-tag \"${{ inputs.upstream_tag }}\"", workflow)
        self.assertIn("runs-on: macos-15", build_job)
        self.assertNotIn("runs-on: macos-15-intel", build_job)
        self.assertIn("uses: actions/cache@v4", build_job)
        self.assertIn("path: ${{ github.workspace }}/.ccache", build_job)
        self.assertIn("CCACHE_DIR: ${{ github.workspace }}/.ccache", build_job)
        self.assertIn("build-ccache-stats", build_job)

    def test_readme_describes_wrapper_repo_only(self) -> None:
        readme = README_PATH.read_text()
        self.assertIn("wrapper repository", readme)
        self.assertIn("GitHub Release", readme)
        self.assertIn("Tencent/ncnn", readme)
        self.assertNotIn("build for android", readme.lower())
        self.assertNotIn("qq", readme.lower())


if __name__ == "__main__":
    unittest.main()
