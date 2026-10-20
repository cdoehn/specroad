"""Passive import preparation with exact original bytes and an explicit policy.

The first adapter covers JUnit's existing complete mapping analysis. Preparing
an import neither publishes Evidence nor authenticates a product run or tool.
"""
from dataclasses import dataclass
from hashlib import sha256

from .._metadata import __version__
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.record_schemas import record_schema
from ._import_candidates import CandidateValue, passive_status
from .evidence_exchange import EvidenceImportError, _encode_candidates, _read_json, _validate
from .junit import JUnitDocument
from .junit_mapping import (JUnitMapping, JUnitMappingRules, JUnitMappingError,
    JUnitExternalIdentifiers, analyze_junit_candidates)


@dataclass(frozen=True, init=False)
class EvidenceImportPreparation(CandidateValue):
    """An immutable decision and its original files, without write authority."""
    _encoded: bytes
    _originals: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError('Use an import preparation adapter with owned inputs')

    @property
    def original_files(self):
        """Detached role-to-bytes map; these are not paths or published files."""
        return dict(self._originals)

    def __bool__(self):
        raise TypeError('Import preparation is not successful verification or write authority')


def _original(raw):
    return {'sha256': sha256(raw).hexdigest(), 'size': len(raw)}


def _tool(value):
    if type(value) is not dict:
        raise EvidenceImportError('explicit_import_tool_required', pointer='/tool')
    try:
        definitions = record_schema('evidence')['$defs']
        _validate(value, {'$ref': '#/$defs/tool', '$defs': definitions})
        return _read_json(canonical_json_bytes(value))
    except ModelError as error:
        raise EvidenceImportError(error.reason, pointer='/tool' + error.pointer) from error


def prepare_junit_import(document, mapping, *, targets, policy, tool,
                         external_identifiers=None):
    """Bind originals and apply abort/skip to every diagnosed JUnit occurrence.

    ``abort_import`` withholds all candidates when any mapping diagnostic is
    present. ``skip_invalid_with_diagnostic`` retains only independently valid
    candidates and all diagnoses. Failed or skipped test outcomes are valid
    observations, not malformed evidence. Global input errors still raise.
    """
    if type(policy) is not str or policy not in ('abort_import', 'skip_invalid_with_diagnostic'):
        raise EvidenceImportError('explicit_import_policy_required', pointer='/policy')
    tool = _tool(tool)
    if type(document) is not JUnitDocument:
        raise JUnitMappingError('typed_junit_document_required')
    if type(mapping) not in (JUnitMapping, JUnitMappingRules):
        raise JUnitMappingError('typed_junit_mapping_required')
    if external_identifiers is not None and type(external_identifiers) is not JUnitExternalIdentifiers:
        raise JUnitMappingError('typed_junit_external_identifiers_required')
    # Own all source bytes before analysis; replaceable decoded caches cannot
    # substitute a different report, mapping, sidecar or provenance descriptor.
    document, mapping = JUnitDocument(document.source_bytes), type(mapping)(mapping.source_bytes)
    sidecar = (None if external_identifiers is None
               else JUnitExternalIdentifiers(external_identifiers.source_bytes))
    analysis = analyze_junit_candidates(
        document, mapping, targets=targets, external_identifiers=sidecar)
    observed = analysis.data
    originals = [('source', document.source_bytes), ('mapping', mapping.source_bytes)]
    external = None
    if sidecar is not None:
        originals.append(('external_identifiers', sidecar.source_bytes))
        external = {**_original(sidecar.source_bytes), 'canonical_sha256': sidecar.sha256,
                    'format_version': sidecar.data['format_version']}
    provenance = {
        'format_version': 'evidence-import-provenance-v1', 'import_format': 'junit',
        'source': _original(document.source_bytes),
        'mapping': {**_original(mapping.source_bytes), 'canonical_sha256': mapping.sha256,
                    'format_version': mapping.data['format_version']},
        'external_identifiers': external, 'parser_profile': observed['parser_profile'],
        'tool': tool, 'importer': {'name': 'specroad', 'version': __version__}}
    provenance_hash = canonical_json_sha256(provenance)
    aborted = policy == 'abort_import' and bool(observed['diagnostics'])
    candidates = [] if aborted else [
        {**candidate, 'provenance_sha256': provenance_hash} for candidate in observed['candidates']]
    value = {
        'format_version': 'evidence-import-preparation-v1', 'import_format': 'junit',
        'policy': policy, 'decision': 'aborted' if aborted else 'prepared',
        'provenance': provenance, 'provenance_sha256': provenance_hash,
        'analysis_sha256': analysis.sha256, 'candidates': candidates,
        'candidate_count': len(candidates), 'testcase_count': observed['testcase_count'],
        'diagnostics': observed['diagnostics'],
        'rejected_testcase_indexes': observed['rejected_testcase_indexes'],
        'withheld_testcase_indexes': (
            [candidate['testcase_index'] for candidate in observed['candidates']] if aborted else []),
        **passive_status(import_policy_applied=True, run_context_bound=False,
                         producer_tool_verified=False)}
    prepared = object.__new__(EvidenceImportPreparation)
    object.__setattr__(prepared, '_encoded', _encode_candidates(value))
    object.__setattr__(prepared, '_originals', tuple(originals))
    return prepared
