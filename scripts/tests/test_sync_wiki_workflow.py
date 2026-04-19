from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "sync-wiki.yml"


class SyncWikiWorkflowTests(unittest.TestCase):
    def test_limits_wiki_sync_to_upstream_repository(self) -> None:
        workflow = WORKFLOW_PATH.read_text()
        self.assertIn("if: github.repository == 'Tencent/ncnn'", workflow)

    def test_skips_push_when_token_is_missing(self) -> None:
        workflow = WORKFLOW_PATH.read_text()
        self.assertIn('WIKI_SYNC_BOT_TOKEN: ${{ secrets.WIKI_SYNC_BOT_TOKEN }}', workflow)
        self.assertIn('if [ -z "$WIKI_SYNC_BOT_TOKEN" ]; then', workflow)
        self.assertIn("WIKI_SYNC_BOT_TOKEN is not configured; skipping wiki sync.", workflow)
        self.assertIn("https://${WIKI_SYNC_BOT_TOKEN}@github.com/Tencent/ncnn.wiki.git", workflow)


if __name__ == "__main__":
    unittest.main()
