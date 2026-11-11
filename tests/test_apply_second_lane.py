from copy import deepcopy
import pytest
from verification_support.bundle_contract import validate_bundle
from test_apply_commit_plan import bundle


def test_explicit_second_branch_is_supported_without_changing_binding():
    data = bundle(); data['branch'] = 'dev2'
    before = deepcopy(data['binding'])
    assert validate_bundle(data)['binding'] == before


@pytest.mark.parametrize('branch', ['main', '', 'DEV2', 'dev3'])
def test_unapproved_branch_is_rejected(branch):
    data = bundle(); data['branch'] = branch
    with pytest.raises(ValueError): validate_bundle(data)


@pytest.mark.parametrize('name,branch,target', [
    ('specroad-dev2', 'dev2', 'specroad-dev2'),
    ('specroad-dev', 'dev', 'specroad-dev'),
    ('specroad-apply2', 'dev', 'specroad-apply2'),
    ('specroad-apply', 'dev2', 'specroad-apply2'),
])
def test_native_apply_location_rejects_dev_copies_wrong_branch_and_wrong_target(tmp_path, name, branch, target):
    from verification_support.bundle_apply import NativeApply
    data = bundle(); data.update(branch='dev2', apply_repository=str(tmp_path/target))
    backend = NativeApply(data)
    backend.root = tmp_path/name
    def git(*args):
        return (str(backend.root) if args[0] == 'rev-parse' else branch).encode()
    backend.git = git
    with pytest.raises(ValueError):
        backend.location()
