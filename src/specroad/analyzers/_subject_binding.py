"""Original subject headers shared by requests and intrinsically checked reports."""
from ..model.domain_fields import NormativeForce
from ..model.language_tags import parse_language_tag
from ..model.paths import ARTIFACT_PATHS, artifact_path
from ..changes._patch_pointer import _pointer as parse_pointer
from ..model.errors import ModelError
from ._values import AnalyzerError, digest, hash_value, require

SUBJECT_BINDING = ('artifact_id', 'artifact_revision', 'artifact_sha256', 'field_pointer')

def _artifact_id(value, at):
    require(type(value) is str, 'analyzer_invalid_artifact_id', at)
    pieces = value.split('-', 2)
    kinds = [kind for kind, (_, prefix) in ARTIFACT_PATHS.items() if len(pieces) == 3 and prefix == pieces[1]]
    require(len(kinds) == 1, 'analyzer_invalid_artifact_id', at)
    try:
        artifact_path(kinds[0], value, pieces[0])
    except ModelError as error:
        raise AnalyzerError('analyzer_invalid_artifact_id', pointer=at) from error


def subject_header(value, at):
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
    require(value['subject_key'] == digest({k:value[k] for k in SUBJECT_BINDING}),
            'analyzer_subject_key_mismatch', at + '/subject_key')
