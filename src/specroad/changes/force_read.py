"""Read original Force completion bytes without promoting them to approval."""
from ._lock_files import LockFiles
from .force_receipts import read_group, completion
from .normal_access import require_normal_access


def read_force_completion(root, transaction_id, *, project_id):
    """Explicit project identity also permits inspecting damaged model bytes."""
    require_normal_access(root, expected_project_id=project_id)
    with LockFiles(root) as files:
        write = read_group(files, transaction_id, project_id=project_id)
        require_normal_access(root, expected_project_id=project_id)
        return completion(write, current=False)
