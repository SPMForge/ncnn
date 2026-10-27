"""Public Releases reserve version names even when their Git tags disappear."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.spm import select_upstream_tag as selector


class ReservedReleaseNamesTests(unittest.TestCase):
    def arguments(self):
        return SimpleNamespace(repo_root=Path('/wrapper'), release_channel='alpha',
                               github_repository='SPMForge/ncnn')

    def test_selector_propagates_shared_candidate(self):
        with patch.object(selector, '_list_refs', return_value=['refs/tags/1.0.20261020-alpha.1']), \
             patch.object(selector.release_inputs, 'find_available_alpha', return_value={
                 'tag': '1.0.20261020-alpha.7', 'occupied_tags': [], 'reason': 'reserved'}) as allocation:
            tags = selector._resolve_release_tags(self.arguments(), '20261020')
        self.assertEqual(tags, ('1.0.20261020-alpha.1', '1.0.20261020-alpha.1', '1.0.20261020-alpha.7'))
        self.assertEqual(allocation.call_args.args[2], '1.0.20261020-alpha.2')

    def test_allocator_failure_aborts_selector(self):
        with patch.object(selector, '_list_refs', return_value=[]), \
             patch.object(selector.release_inputs, 'find_available_alpha', side_effect=RuntimeError('HTTP 503')):
            with self.assertRaisesRegex(RuntimeError, '503'):
                selector._resolve_release_tags(self.arguments(), '20261020')
