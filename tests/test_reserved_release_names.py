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

    def test_orphan_releases_reserve_every_occupied_alpha_name(self):
        with patch.object(selector, '_list_refs', return_value=['refs/tags/1.0.20261020-alpha.1']), \
             patch('scripts.release_inputs.github_json', side_effect=[{'id': n} for n in range(2, 7)] + [None]) as api:
            tags = selector._resolve_release_tags(self.arguments(), '20261020')
        self.assertEqual(tags, ('1.0.20261020-alpha.1', '1.0.20261020-alpha.1', '1.0.20261020-alpha.7'))
        self.assertEqual(len(api.call_args_list), 6)

    def test_release_api_failure_never_authorizes_a_version_name(self):
        with patch.object(selector, '_list_refs', return_value=[]), \
             patch('scripts.release_inputs.github_json', side_effect=RuntimeError('HTTP 503')):
            with self.assertRaisesRegex(RuntimeError, '503'):
                selector._resolve_release_tags(self.arguments(), '20261020')
