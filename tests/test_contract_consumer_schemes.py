"""Keep each mergeable consumer executable's embedding graph independent."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.spm import validate_package_contract as contract


class ContractConsumerSchemeTests(unittest.TestCase):
    def test_builds_each_executable_scheme_and_runs_both_configurations(self):
        release = SimpleNamespace(build_metadata=SimpleNamespace(
            release_asset=SimpleNamespace(variant=SimpleNamespace(target_name='ncnn_vulkan'))))
        with patch.object(contract, '_write_consumer_package', return_value='Probe'), patch.object(contract, '_run') as run:
            contract._validate_local_package_consumers(Path('/local-sdk'), 'ncnn', [release])
        commands = [call.args[0] for call in run.call_args_list]
        builds = [command for command in commands if command[0] == 'xcodebuild']
        self.assertEqual([command[command.index('-scheme') + 1] for command in builds], ['SmokeSwift', 'Smoke'])
        for command in builds:
            self.assertIn('MERGED_BINARY_TYPE=automatic', command)
        executions = [command for command in commands if command[:2] == ['swift', 'run']]
        self.assertEqual({(command[3], command[4]) for command in executions},
                         {('debug', 'SmokeSwift'), ('debug', 'Smoke'),
                          ('release', 'SmokeSwift'), ('release', 'Smoke')})
