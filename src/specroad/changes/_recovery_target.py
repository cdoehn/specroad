"""Read-only proof of a fully published recovery target."""
from ..model.canonical import canonical_json_bytes
from ..security import SafetyViolation
from .committing_values import CommittingJournal
from .execution_values import ChangeExecutionError
from .recovery_values import RecoveryError
from ._staging_files import _image


def prove_complete_target(files, journal):
    """Prove every journal-bound target file without loading the project model."""
    tokens = {}
    for item in journal.data['target_inventory']:
        parts = tuple(item['path'].split('/'))
        with files.directory(parts[:-1]) as directory:
            if directory is None:
                raise RecoveryError('recovery_target_missing', path=item['path'], exit_code=6)
            try:
                identity = _image(directory, parts[-1], item['size'], item['sha256'])
            except (ChangeExecutionError, OSError, SafetyViolation) as error:
                raise RecoveryError('recovery_target_mismatch', path=item['path'], exit_code=6) from error
            tokens[item['path']] = {
                'identity': identity,
                'size': item['size'],
                'sha256': item['sha256'],
            }
    return tokens


def fully_published(journal):
    """Project a committing journal to the state implied by a proven full target."""
    value = journal.data
    value['published_count'] = len(value['files'])
    for entry in value['files']:
        entry['published'] = True
    return CommittingJournal(canonical_json_bytes(value))
