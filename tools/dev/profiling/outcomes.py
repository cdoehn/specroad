"""Native selected-run proof, separate from process orchestration."""
from verification_support.host_execution import verify_resources


def check_observation(observation, pairs, code, resources):
    if (not pairs or not isinstance(observation, dict) or code != 0 or observation.get('pytest_exit_code') != 0 or
            observation.get('suite_passed') is not True or observation.get('errors') != [] or
            observation.get('nodeid_to_test_id') != pairs or observation.get('tests_run') != len(pairs) or
            observation.get('test_outcomes') != dict.fromkeys(pairs.values(), 'passed')):
        raise ValueError('Native observations do not prove this complete selected run passed')
    verify_resources(observation, resources)
