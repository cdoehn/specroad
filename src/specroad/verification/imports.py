"""Passive JUnit, Generic and SARIF preparation with explicit import policy.

Preparing an import neither publishes Evidence nor authenticates a run or tool.
"""
from dataclasses import dataclass
from hashlib import sha256

from .._metadata import __version__
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.record_schemas import record_schema
from ._import_candidates import CandidateValue
from ._import_analysis import _input_bytes, _generic_analysis, _sarif_analysis
from ._import_policy import _policy, _junit_policy, _record_policy
from .evidence_exchange import EvidenceExchange, EvidenceImportError, _encode_candidates, _read_json, _validate
from .junit import JUnitDocument
from .junit_mapping import (JUnitMapping, JUnitMappingRules, JUnitMappingError,
    JUnitExternalIdentifiers, analyze_junit_candidates)
from .sarif import SarifDocument, SarifMapping


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


def _preparation(data, originals):
    """Freeze the decided output and retain the exact original file roles."""
    prepared = object.__new__(EvidenceImportPreparation)
    object.__setattr__(prepared, '_encoded', _encode_candidates(data))
    object.__setattr__(prepared, '_originals', tuple(originals))
    return prepared


def prepare_junit_import(document, mapping, *, targets, policy, tool,
                         external_identifiers=None):
    """Bind originals and apply abort/skip to every diagnosed JUnit occurrence.

    ``abort_import`` withholds all candidates when any mapping diagnostic is
    present. ``skip_invalid_with_diagnostic`` retains only independently valid
    candidates and all diagnoses. Failed or skipped test outcomes are valid
    observations, not malformed evidence. Global input errors still raise.
    """
    _policy(policy)
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
    return _preparation(_junit_policy(observed, provenance, analysis, policy), originals)


def _prepare_records(format_name, originals, mapping, profile, tool, candidates,
                     diagnostics, occurrences):
    accepted = [c['source_pointer'] for c in candidates]
    rejected = {p for d in diagnostics for p in d['occurrences']}
    if (len(accepted) != len(set(accepted)) or set(accepted) & rejected
            or set(accepted) | rejected != set(occurrences)):
        raise EvidenceImportError('import_occurrence_accounting_mismatch')
    provenance = {
        'format_version': 'evidence-import-provenance-v1', 'import_format': format_name,
        'source': _original(originals[0][1]), 'mapping': mapping,
        'external_identifiers': None, 'parser_profile': profile, 'tool': tool,
        'importer': {'name': 'specroad', 'version': __version__}}
    analysis = {'candidates': candidates, 'diagnostics': diagnostics, 'occurrences': occurrences}
    return provenance, analysis


def prepare_generic_import(exchange, *, targets, policy):
    """Prepare exact Exchange bytes; record-local errors obey the given policy.

    Accept an existing EvidenceExchange or original bytes, including records
    whose missing/invalid required fields must be diagnosed individually.
    Global envelope, target and resource errors remain fatal for either policy.
    The Exchange itself contains the explicit target/check/test/subject mapping.
    """
    _policy(policy)
    raw = _input_bytes(exchange, EvidenceExchange)
    value, candidates, diagnostics = _generic_analysis(raw, targets)
    originals = [('source', raw)]
    mapping = {**_original(raw), 'canonical_sha256': canonical_json_sha256(value),
               'format_version': value['format_version'], 'source_role': 'source'}
    for candidate in candidates:
        candidate['source_pointer'] = '/results/' + str(candidate['result_index'])
    for diagnostic in diagnostics:
        diagnostic.update(input_role='source', occurrences=[
            '/results/' + str(n) for n in diagnostic['result_indexes']])
    occurrences = ['/results/' + str(n) for n in range(len(value['results']))]
    provenance, analysis = _prepare_records('generic', originals, mapping,
        value['format_version'], value['tool'], candidates, diagnostics, occurrences)
    return _preparation(_record_policy('generic', provenance, analysis, policy), originals)


def prepare_sarif_import(document, mapping, *, targets, policy):
    """Prepare mapped inline observations; diagnose every omitted occurrence.

    Typed inputs or original bytes are accepted. Ambiguous/invalid mapping
    rows, invalid required Exchange records and selected SARIF errors are
    collected without letting any one of them select a favorable observation.
    """
    _policy(policy)
    raw = _input_bytes(document, SarifDocument)
    mapping_raw = _input_bytes(mapping, SarifMapping)
    settings, exchange, candidates, diagnostics, occurrences = _sarif_analysis(raw, mapping_raw, targets)
    originals = [('source', raw), ('mapping', mapping_raw)]
    mapping_binding = {**_original(mapping_raw), 'canonical_sha256': canonical_json_sha256(settings),
                       'format_version': settings['format_version']}
    provenance, analysis = _prepare_records('sarif', originals, mapping_binding,
        'sarif-inline-2.1.0-v1', exchange['tool'], candidates, diagnostics, occurrences)
    return _preparation(_record_policy('sarif', provenance, analysis, policy), originals)
