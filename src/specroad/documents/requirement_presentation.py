"""Bound, separate requirement meaning and presentation metadata.

The original statement is never a template or input to language inference.
Only explicitly supplied model resources can contribute display labels.
"""
from dataclasses import dataclass
from hashlib import sha256

from .._metadata import __version__, MODEL_SCHEMA_VERSION
from ..model.language_labels import label_for
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.content_language import ContentLanguage
from ..model.errors import ModelError
from ..model.language_packages import select_language_packages
from ..storage.json_syntax import parse_json_object
from ..storage.requirement import RequirementArtifact


class RequirementPresentationError(ModelError):
    exit_code = 3


@dataclass(frozen=True, init=False)
class RequirementPresentation:
    """Detached render data and original source bytes; not semantic approval."""
    _encoded: bytes
    source_bytes: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resolve_requirement_presentation with an owned TargetModel')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Requirement presentation is not semantic or release approval')


def resolve_requirement_presentation(model, requirement_id):
    """Bind explicit meaning and independent language/direction declarations.

    This checks the selected requirement's fields. It does not validate the
    entire project, language policy, registry membership or natural language.
    No host locale, detector, translation or implicit resource loading is used.
    """
    from ..changes.target_model import TargetModel, _default_scope
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    if type(requirement_id) is not str:
        raise RequirementPresentationError('presentation_requirement_id_required', pointer='/requirement_id')
    model = model.snapshot()
    records = [SourceRelations(d.content, path=d.path) for d in model.documents]
    source = next((r for r in records if r.identity.id == requirement_id), None)
    if source is None:
        raise RequirementPresentationError('presentation_requirement_not_found', pointer='/requirement_id')
    if source.identity.artifact_type != 'requirement':
        raise RequirementPresentationError('presentation_requirement_required', path=source.path,
                                           pointer='/requirement_id')
    requirement = RequirementArtifact(source.source_bytes, path=source.path)
    value, meaning = requirement.data, requirement.meaning
    content_language = ContentLanguage(meaning.language, value.get('text_direction', 'auto'))
    locale = model.configuration.data['default_locale']
    packages = select_language_packages(locale, model.language_packages)
    force = meaning.normative_force.value
    data = {'format_version': 1, 'kind': 'requirement-presentation-v1',
        'generated': True, 'normative': False, 'tool_version': __version__,
        'schema_version': MODEL_SCHEMA_VERSION, 'profiles': list(model.profile.profile_chain),
        'project_id': model.binding.project_id,
        'model_root_sha256': model.manifest(model.artifacts, _default_scope()).sha256,
        'input_sha256': model._sources_sha256,
        'requirement': {'artifact_id': requirement_id, 'revision': value['revision'],
            'path': source.path, 'source_sha256': sha256(requirement.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(value)},
        'statement': meaning.statement,
        'statement_utf8_sha256': sha256(meaning.statement.encode('utf-8')).hexdigest(),
        'normative_force': force, 'content_language': content_language.as_dict(),
        'text_direction_source': 'declaration' if 'text_direction' in value else 'default',
        'display_locale': locale, 'label_packages': [p.binding() for p in packages],
        'force_label': label_for(force, domain='normative_force', packages=packages),
        'validation_scope': 'supplied_requirement_fields',
        'project_files_verified': False, 'full_validation_passed': False,
        'language_policy_evaluated': False, 'language_registry_checked': False,
        'text_semantics_evaluated': False, 'translation_performed': False,
        'rendering_performed': False, 'write_authorized': False, 'approval_granted': False}
    result = object.__new__(RequirementPresentation)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    object.__setattr__(result, 'source_bytes', requirement.source_bytes)
    return result
