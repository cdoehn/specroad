"""Validate the entire supplied snapshot without reading a project or a path."""
import re

from ..model.domain_fields import NormativeForce
from ..model.language_tags import parse_language_tag
from ..model.paths import ARTIFACT_PATHS, artifact_path
from ..changes._patch_pointer import _pointer as parse_pointer
from ..model.errors import ModelError
from .descriptors import AnalyzerDescriptor
from ._values import (AnalyzerError, digest, encoded, extensions, hash_value,
                      require, shape)

SNAPSHOT_FIELDS = ('contract_version', 'analyzers', 'subjects', 'context', 'settings', 'extensions')
SUBJECT_BINDING = ('artifact_id', 'artifact_revision', 'artifact_sha256', 'field_pointer')
REQUEST_FIELDS = frozenset((*SNAPSHOT_FIELDS, 'request_id', 'snapshot_sha256'))
RESOURCE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')


def _array(value, at, *, nonempty=False):
    require(type(value) is list and (bool(value) or not nonempty), 'analyzer_array_required', at)


def _artifact_id(value, at):
    require(type(value) is str, 'analyzer_invalid_artifact_id', at)
    pieces = value.split('-', 2)
    kinds = [kind for kind, (_, prefix) in ARTIFACT_PATHS.items() if len(pieces) == 3 and prefix == pieces[1]]
    require(len(kinds) == 1, 'analyzer_invalid_artifact_id', at)
    try:
        artifact_path(kinds[0], value, pieces[0])
    except ModelError as error:
        raise AnalyzerError('analyzer_invalid_artifact_id', pointer=at) from error


def _subject(value, at, *, text_only):
    shape(value, (*SUBJECT_BINDING, 'subject_key', 'value', 'value_sha256', 'declared_language'),
          at, optional=('normative_force',))
    _artifact_id(value['artifact_id'], at + '/artifact_id')
    require(type(value['artifact_revision']) is int and value['artifact_revision'] > 0,
            'analyzer_invalid_revision', at + '/artifact_revision')
    for field in ('artifact_sha256', 'subject_key', 'value_sha256'):
        hash_value(value[field], at + '/' + field)
    try:
        parse_pointer(value['field_pointer'], at + '/field_pointer')
    except ModelError as error:
        raise AnalyzerError(error.reason, pointer=error.pointer) from error
    try:
        parse_language_tag(value['declared_language'])
    except ModelError as error:
        raise AnalyzerError(error.reason, pointer=at + '/declared_language') from error
    if 'normative_force' in value:
        try:
            NormativeForce.from_value(value['normative_force'])
        except ModelError as error:
            raise AnalyzerError(error.reason, pointer=at + '/normative_force') from error
    require(not text_only or type(value['value']) is str, 'analyzer_text_subject_required', at + '/value')
    require(value['subject_key'] == digest({k:value[k] for k in SUBJECT_BINDING}),
            'analyzer_subject_key_mismatch', at + '/subject_key')
    require(value['value_sha256'] == digest(value['value']),
            'analyzer_value_hash_mismatch', at + '/value_sha256')


def validate_snapshot(value):
    shape(value, REQUEST_FIELDS)
    require(value['contract_version'] == '1.0.0', 'analyzer_unsupported_contract', '/contract_version')
    entries = value['analyzers']
    _array(entries, '/analyzers', nonempty=True)
    names, text_only = [], False
    for index, entry in enumerate(entries):
        at = '/analyzers/' + str(index)
        shape(entry, ('descriptor', 'descriptor_sha256', 'capabilities'), at)
        descriptor = AnalyzerDescriptor(encoded(entry['descriptor']))
        hash_value(entry['descriptor_sha256'], at + '/descriptor_sha256')
        require(entry['descriptor_sha256'] == descriptor.sha256, 'analyzer_descriptor_hash_mismatch', at)
        capabilities = descriptor.select_capabilities(entry['capabilities'])
        text_only = text_only or 'language_detection' in capabilities
        names.append(descriptor.data['analyzer_id'])
    require(names == sorted(set(names)), 'analyzer_sorted_unique_required', '/analyzers')
    subjects = value['subjects']
    _array(subjects, '/subjects', nonempty=True)
    for index, subject in enumerate(subjects):
        _subject(subject, '/subjects/' + str(index), text_only=text_only)
    keys = [s['subject_key'] for s in subjects]
    require(len(set(keys)) == len(keys), 'analyzer_duplicate_subject', '/subjects')
    context = value['context']
    shape(context, ('resources', 'subject_keys'), '/context')
    require(type(context['subject_keys']) is list and context['subject_keys'] == sorted(keys),
            'analyzer_context_subjects_mismatch', '/context/subject_keys')
    _array(context['resources'], '/context/resources')
    resources = []
    for index, item in enumerate(context['resources']):
        at = '/context/resources/' + str(index)
        shape(item, ('resource_id', 'sha256', 'value'), at)
        require(type(item['resource_id']) is str and RESOURCE_ID.fullmatch(item['resource_id']) is not None,
                'analyzer_invalid_resource_id', at)
        hash_value(item['sha256'], at + '/sha256')
        require(item['sha256'] == digest(item['value']), 'analyzer_context_hash_mismatch', at)
        resources.append(item['resource_id'])
    require(resources == sorted(set(resources)), 'analyzer_sorted_unique_required', '/context/resources')
    require(type(value['settings']) is dict and set(value['settings']) == set(names),
            'analyzer_settings_binding_mismatch', '/settings')
    require(all(type(item) is dict for item in value['settings'].values()),
            'analyzer_settings_object_required', '/settings')
    extensions(value['extensions'])
