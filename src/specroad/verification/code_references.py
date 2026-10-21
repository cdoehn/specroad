"""Language-neutral code bytes from an explicit safe local or Git source."""
from dataclasses import dataclass, field
from hashlib import new as new_hash, sha256
import os

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import ProjectBoundary, SafetyViolation
from ..security.resource_access import opened_resource
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact


@dataclass(frozen=True, init=False)
class CodeReferenceSource:
    """Owned original bytes and their binding, not a code currency decision."""
    source_bytes: bytes = field(repr=False)
    _encoded: bytes = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError('Use read_code_reference')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Source bytes are not a currency or approval decision')


def read_code_reference(source, reference):
    """Bind one stored code_ref to bytes, without checkout, decoding or execution.

    Source choice is explicit: ProjectBoundary reads the working file;
    GitObjectSource reads its bound commit tree. Stored Git identities require
    that Git source and must match it exactly; never fall back to HEAD or disk.
    Selectors and hints remain data. H.2/H.3 evaluation is a separate operation.
    """
    # Keep the public query and verification package imports independent.
    from ..query.git_source import GitObjectSource

    if type(reference) is not RecordArtifact:
        raise ModelError('code_reference_record_required')
    record = RecordArtifact(reference.source_bytes, expected_type='code_ref', path=reference.path)
    value = record.data
    if type(source) not in (ProjectBoundary, GitObjectSource):
        raise ModelError('code_reference_source_required')
    git_commit = git_blob = None
    if type(source) is GitObjectSource:
        git_commit = source.commit_id
        if 'git_commit' in value and value['git_commit'] != git_commit:
            raise ModelError('code_reference_git_commit_mismatch', pointer='/git_commit')
        raw = source.read_bytes(value['path'])
        header = b'blob ' + str(len(raw)).encode('ascii') + b'\0'
        git_blob = new_hash('sha1' if len(git_commit) == 40 else 'sha256',
                            header + raw, usedforsecurity=False).hexdigest()
        if 'git_blob' in value and value['git_blob'] != git_blob:
            raise ModelError('code_reference_git_blob_mismatch', pointer='/git_blob')
    else:
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
    file_sha256 = sha256(raw).hexdigest()
    report = {'format_version': 'code-reference-source-v1',
        'validation_scope': 'code_reference_source_bytes_only',
        'reference': value, 'reference_sha256': sha256(record.source_bytes).hexdigest(),
        'source_kind': 'git' if git_commit is not None else 'file',
        'path': value['path'], 'size': len(raw), 'file_sha256': file_sha256,
        'file_hash_matches': file_sha256 == value['file_sha256'],
        'git_commit': git_commit, 'git_blob': git_blob,
        'selection_evaluated': False, 'reference_state_evaluated': False,
        'symbol_resolved': False, 'source_code_executed': False,
        'write_authorized': False}
    result = object.__new__(CodeReferenceSource)
    object.__setattr__(result, 'source_bytes', raw)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
