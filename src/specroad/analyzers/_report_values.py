"""Closed generic report checks. Adapter payloads remain passive observations."""
import re

from ..model.identity_tokens import decode128
from ..model.errors import ModelError
from ._values import AnalyzerError, extensions, hash_value, require, shape

STATES = ('done', 'undetermined', 'failed', 'open')
ENGINE_FACTS = ('library_versions', 'model_sha256', 'candidates', 'candidates_sha256',
                'preprocessing_version', 'unicode_version', 'runtime_fingerprint', 'numpy_fingerprint')


def _text(value, at):
    require(type(value) is str and bool(value.strip()), 'analyzer_nonempty_text_required', at)


def run_identity(value):
    require(type(value) is str and value.startswith('AR-'), 'analyzer_invalid_run_id', '/run_id')
    try:
        decode128(value[3:])
    except ModelError as error:
        raise AnalyzerError('analyzer_invalid_run_id', pointer='/run_id') from error


def engine_values(value, analyzer):
    shape(value, ('adapter_version', *ENGINE_FACTS), '/engine')
    require(value['adapter_version'] == analyzer['descriptor']['adapter_version'],
            'analyzer_engine_adapter_mismatch', '/engine/adapter_version')
    for key in ENGINE_FACTS:
        at = '/engine/' + key
        fact = value[key]
        shape(fact, ('value', 'reason'), at)
        if fact['value'] is None:
            _text(fact['reason'], at + '/reason')
        else:
            require(fact['reason'] is None, 'analyzer_known_fact_reason', at)
            item = fact['value']
            if key.endswith('sha256'):
                hash_value(item, at + '/value')
            elif key == 'candidates':
                require(type(item) is list and bool(item) and all(type(x) is str and x for x in item),
                        'analyzer_invalid_candidates', at)
                require(len(set(item)) == len(item), 'analyzer_duplicate_candidate', at)
            elif key == 'library_versions':
                require(type(item) is dict and bool(item), 'analyzer_invalid_libraries', at)
                for name, version in item.items():
                    _text(name, at); _text(version, at)
            elif key in ('runtime_fingerprint', 'numpy_fingerprint'):
                # Opaque hash of a separately declared actual runtime inventory.
                hash_value(item, at + '/value')
            else:
                _text(item, at + '/value')
    candidates = value['candidates']['value']
    from ._values import digest
    require(value['candidates_sha256']['value'] == (None if candidates is None else digest(candidates)),
            'analyzer_candidate_hash_mismatch', '/engine/candidates_sha256')


def exact_coverage(subjects):
    coverage = {'expected':sorted(s['subject_key'] for s in subjects)}
    coverage.update({status:sorted(s['subject_key'] for s in subjects if s['status'] == status)
                     for status in STATES})
    coverage['counts'] = {key:len(items) for key, items in coverage.items()}
    return coverage


def check_findings(value, keys):
    require(type(value) is list, 'analyzer_findings_array_required', '/findings')
    findings = {}
    for index, item in enumerate(value):
        at = '/findings/' + str(index)
        shape(item, ('finding_id', 'code', 'severity', 'subject_keys', 'message', 'rationale', 'details'),
              at, optional=('suggestion',))
        identity = item['finding_id']
        _text(identity, at + '/finding_id')
        require(identity not in findings, 'analyzer_duplicate_finding', at)
        extensions({item['code']:None}, at + '/code') if type(item['code']) is str else require(False, 'analyzer_invalid_namespace', at)
        require(type(item['severity']) is str and item['severity'] in ('info', 'warning', 'error'),
                'analyzer_invalid_severity', at)
        _text(item['message'], at + '/message'); _text(item['rationale'], at + '/rationale')
        members = item['subject_keys']
        require(type(members) is list and all(type(k) is str for k in members), 'analyzer_invalid_finding_subjects', at)
        require(members == sorted(set(members)) and set(members) <= keys, 'analyzer_foreign_finding_subject', at)
        extensions(item['details'], at + '/details')
        for detail in item['details'].values():
            shape(detail, ('kind', 'value'), at + '/details', optional=('score_semantics',))
            if detail['kind'] == 'score':
                _text(detail.get('score_semantics'), at + '/details/score_semantics')
                require(type(detail['value']) is str and re.fullmatch(
                    r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', detail['value']) is not None,
                    'analyzer_invalid_score', at + '/details/value')
            else:
                require(detail['kind'] == 'json' and 'score_semantics' not in detail,
                        'analyzer_invalid_detail_kind', at + '/details')
        findings[identity] = item
    return findings


def report_subjects(subjects, request, findings):
    require(type(subjects) is list, 'analyzer_subject_results_required', '/subjects')
    originals = {s['subject_key']:{k:v for k,v in s.items() if k != 'value'} for s in request['subjects']}
    seen = set()
    for index, subject in enumerate(subjects):
        at = '/subjects/' + str(index)
        require(type(subject) is dict and type(subject.get('subject_key')) is str,
                'analyzer_subject_result_required', at)
        key = subject['subject_key']
        require(key in originals and key not in seen, 'analyzer_result_subject_mismatch', at)
        original = originals[key]
        shape(subject, (*original, 'status', 'payload'), at, optional=('findings',))
        require({k:subject[k] for k in original} == original, 'analyzer_original_binding_mismatch', at)
        require(type(subject['artifact_revision']) is int, 'analyzer_invalid_revision', at)
        require(type(subject['status']) is str and subject['status'] in STATES, 'analyzer_invalid_subject_status', at)
        extensions(subject['payload'], at + '/payload')
        refs = subject.get('findings', [])
        require(type(refs) is list and all(type(ref) is str for ref in refs), 'analyzer_invalid_finding_refs', at)
        require(refs == sorted(set(refs)) and all(ref in findings and key in findings[ref]['subject_keys'] for ref in refs),
                'analyzer_finding_reference_mismatch', at)
        seen.add(key)
    require(seen == set(originals), 'analyzer_result_subject_mismatch', '/subjects')
    require([s['subject_key'] for s in subjects] == sorted(seen), 'analyzer_sorted_results_required', '/subjects')


def coverage_status(value):
    coverage = value['coverage']
    shape(coverage, ('expected', *STATES, 'counts'), '/coverage')
    shape(coverage['counts'], ('expected', *STATES), '/coverage/counts')
    require(all(type(n) is int and n >= 0 for n in coverage['counts'].values()),
            'analyzer_invalid_coverage_count', '/coverage/counts')
    require(coverage == exact_coverage(value['subjects']), 'analyzer_coverage_mismatch', '/coverage')
    status = value['run_status']
    require(type(status) is str and status in ('complete', 'partial', 'failed', 'unavailable'),
            'analyzer_invalid_run_status', '/run_status')
    allowed = {'complete':not coverage['failed'] and not coverage['open'],
               'partial':bool(coverage['open']), 'failed':bool(coverage['failed']),
               'unavailable':coverage['open'] == coverage['expected']}
    require(allowed[status], 'analyzer_run_coverage_mismatch', '/run_status')
