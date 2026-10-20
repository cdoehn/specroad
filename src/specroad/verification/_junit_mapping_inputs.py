"""Passive JUnit mapping input readers and parser-value projections.

These helpers receive owned input values. They have no native target lookup,
Evidence assignment, diagnostic policy, external resolver or publication path.
The public caller supplies its existing error type to preserve that contract
without creating a circular dependency on the mapping orchestration module.
"""
import re

from ..storage.json_syntax import parse_json_object


def read_mapping(raw, *, version, fields_supported, unique, error_type):
    if type(raw) is not bytes:
        raise error_type('junit_mapping_bytes_required')
    if len(raw) > 4 * 1024 * 1024:
        raise error_type('junit_mapping_byte_limit')
    value = parse_json_object(raw)
    if set(value) != {'format_version', 'identity_fields', 'bindings'}:
        raise error_type('invalid_junit_mapping_fields')
    if value['format_version'] != version:
        raise error_type('unsupported_junit_mapping_version', pointer='/format_version')
    fields = value['identity_fields']
    if (type(fields) is not list or not fields or
            any(type(name) is not str or name not in fields_supported for name in fields) or
            len(set(fields)) != len(fields)):
        raise error_type('invalid_junit_identity_fields', pointer='/identity_fields')
    bindings = value['bindings']
    if type(bindings) is not list or len(bindings) > 10000:
        raise error_type('invalid_junit_mapping_bindings', pointer='/bindings')
    seen = set()
    for number, binding in enumerate(bindings):
        pointer = '/bindings/' + str(number)
        if type(binding) is not dict or set(binding) != {'identity', 'target_id'}:
            raise error_type('invalid_junit_mapping_binding', pointer=pointer)
        identity = binding['identity']
        if (type(identity) is not dict or set(identity) != set(fields) or
                any(type(item) is not str or not item for item in identity.values())):
            raise error_type('invalid_junit_mapping_identity', pointer=pointer + '/identity')
        if type(binding['target_id']) is not str or not binding['target_id']:
            raise error_type('invalid_junit_mapping_target', pointer=pointer + '/target_id')
        key = tuple(identity[name] for name in fields)
        if unique and key in seen:
            raise error_type('duplicate_junit_mapping_identity', pointer=pointer + '/identity')
        seen.add(key)
    return value


def read_external_identifiers(raw, *, error_type):
    if type(raw) is not bytes:
        raise error_type('junit_external_identifiers_bytes_required')
    if len(raw) > 4 * 1024 * 1024:
        raise error_type('junit_external_identifiers_byte_limit')
    value = parse_json_object(raw)
    if set(value) != {'format_version', 'source_sha256', 'entries'}:
        raise error_type('invalid_junit_external_identifiers_fields')
    if value['format_version'] != 'junit-external-identifiers-v1':
        raise error_type('unsupported_junit_external_identifiers_version',
                         pointer='/format_version')
    if (type(value['source_sha256']) is not str or
            re.fullmatch('[0-9a-f]{64}', value['source_sha256']) is None):
        raise error_type('invalid_junit_external_source_hash', pointer='/source_sha256')
    if type(value['entries']) is not list or len(value['entries']) > 10000:
        raise error_type('invalid_junit_external_entries', pointer='/entries')
    seen = set()
    for number, entry in enumerate(value['entries']):
        pointer = '/entries/' + str(number)
        if type(entry) is not dict or set(entry) != {'testcase_index', 'external_id'}:
            raise error_type('invalid_junit_external_entry', pointer=pointer)
        index = entry['testcase_index']
        if type(index) is not int or not 0 <= index < 10000:
            raise error_type('invalid_junit_external_index', pointer=pointer + '/testcase_index')
        if type(entry['external_id']) is not str or not entry['external_id']:
            raise error_type('invalid_junit_external_id', pointer=pointer + '/external_id')
        if index in seen:
            raise error_type('duplicate_junit_external_index', pointer=pointer + '/testcase_index')
        seen.add(index)
    return value


def iter_testcases(parsed):
    """Visit only parsed core occurrences in their original document order."""
    pending = [(parsed['root'], '/root')]
    while pending:
        node, pointer = pending.pop()
        if node['tag'] != 'testcase':
            pending.extend((child, pointer + '/children/' + str(number))
                           for number, child in reversed(list(enumerate(node['children']))))
            continue
        yield node, pointer


def outcome_kinds(node):
    """Observe core outcome tags without choosing a native result or target."""
    return {child['tag'] for child in node['children']
            if child['tag'] in ('failure', 'error', 'skipped')}


def observations(parsed, fields, external):
    """Project explicit identities and contexts; do not interpret mapping rules."""
    cases, groups = [], {}
    for node, pointer in iter_testcases(parsed):
        index = len(cases)
        context = {name: node['attributes'].get(name) for name in ('classname', 'name', 'file')}
        context['external_id'] = external.get(index)
        identity = {name: context[name] for name in fields}
        outcomes = sorted(outcome_kinds(node)) or ['passed']
        cases.append({'testcase_index': index, 'testcase_pointer': pointer,
                      'identity': identity, 'context': context, 'junit_outcomes': outcomes})
        groups.setdefault(tuple(identity.values()), []).append(index)
    return cases, groups
