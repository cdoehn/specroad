"""Native source adapters for an admitted reader and validated code_ref fields."""
from hashlib import new as new_hash
import os

from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security.resource_access import opened_resource


def read_file_source(source, value):
    """Keep the native attachment guard active until all source bytes are read."""
    if 'git_commit' in value or 'git_blob' in value:
        raise ModelError('code_reference_git_source_required')
    # Use the attachment boundary for the entire read, including its final
    # nested-root and descriptor checks. A new specroad.json in a parent
    # directory during the read must invalidate the observation too.
    with opened_resource(source, value['path']) as (descriptor, initial):
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            raw = stream.read()
        if len(raw) != initial.st_size:
            raise SafetyViolation('Code source changed during the read')
    return raw


def read_git_source(source, value):
    """Bind the native Git reader's bytes to the stored optional identities."""
    git_commit = source.commit_id
    if 'git_commit' in value and value['git_commit'] != git_commit:
        raise ModelError('code_reference_git_commit_mismatch', pointer='/git_commit')
    raw = source.read_bytes(value['path'])
    header = b'blob ' + str(len(raw)).encode('ascii') + b'\0'
    git_blob = new_hash('sha1' if len(git_commit) == 40 else 'sha256',
                        header + raw, usedforsecurity=False).hexdigest()
    if 'git_blob' in value and value['git_blob'] != git_blob:
        raise ModelError('code_reference_git_blob_mismatch', pointer='/git_blob')
    return raw, git_commit, git_blob
