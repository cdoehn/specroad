"""Disjoint H.3 decisions over native code sources and exact H.2 selections."""
from dataclasses import dataclass, field
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import ProjectBoundary
from ..security.resource_access import opened_resource
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from ._code_reference_decision import decide_code_state
from .code_references import read_code_reference
from .code_relocation import locate_code_selection


@dataclass(frozen=True, init=False)
class CodeReferenceState:
    """A detached reference state, not approval or permission to rewrite it."""
    _encoded: bytes = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_code_reference')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('A code reference state is not approval or write authority')


def assess_code_reference(source, reference):
    """Evaluate the first applicable H.3 row without updating the stored record.

    Native working files and already bound Git trees are explicit capabilities.
    Missing paths/objects are observed separately from source corruption or
    read/decoding/selector errors, which remain errors, never guessed currency.
    """
    from ..query.git_source import GitObjectSource

    if type(reference) is not RecordArtifact:
        raise ModelError('code_reference_record_required')
    record = RecordArtifact(reference.source_bytes, expected_type='code_ref', path=reference.path)
    value = record.data
    if type(source) not in (ProjectBoundary, GitObjectSource):
        raise ModelError('code_reference_source_required')
    bound = None
    if type(source) is ProjectBoundary:
        if 'git_commit' in value or 'git_blob' in value:
            raise ModelError('code_reference_git_source_required')
        with opened_resource(source, value['path'], missing_ok=True) as (descriptor, _):
            missing = descriptor is None
        if not missing:
            bound = read_code_reference(source, record)
    else:
        if 'git_commit' in value and value['git_commit'] != source.commit_id:
            raise ModelError('code_reference_git_commit_mismatch', pointer='/git_commit')
        if source.read_optional_bytes(value['path']) is not None:
            bound = read_code_reference(source, record)

    location = None
    if bound is not None and value['reference_kind'] in ('line_range', 'text_anchor'):
        location = locate_code_selection(bound)
    observed = None if bound is None else bound.data
    selected = None if location is None else location.data
    state, reason, diagnostics = decide_code_state(
        value['reference_kind'], target_present=bound is not None,
        file_hash_matches=None if observed is None else observed['file_hash_matches'],
        selection_result=None if selected is None else selected['selection_result'])
    new_position = selected['new_position'] if state == 'relocated' else None

    report = {'format_version': 'code-reference-state-v1',
        'validation_scope': 'code_reference_state_only',
        'reference': value, 'reference_sha256': sha256(record.source_bytes).hexdigest(),
        'source_kind': 'git' if type(source) is GitObjectSource else 'file',
        'path': value['path'],
        'git_commit': source.commit_id if type(source) is GitObjectSource else None,
        'target_present': bound is not None,
        'source': observed,
        'source_sha256': None if bound is None else bound.sha256,
        'selection_location': selected,
        'selection_location_sha256': None if location is None else location.sha256,
        'state': state, 'reason': reason, 'diagnostics': diagnostics,
        'new_position': new_position, 'selection_evaluated': location is not None,
        'reference_state_evaluated': True, 'symbol_resolved': False,
        'source_code_executed': False, 'write_authorized': False}
    result = object.__new__(CodeReferenceState)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
