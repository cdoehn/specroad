"""Passive Proposal explanation shapes; neither provenance nor grants are verified."""
from .domain_fields import reference_schema
from .metadata_fields import provenance_schema
from ._field_shapes import _object, _array
from .errors import ModelError

MODEL_FIELDS = ('provider', 'model_name', 'model_version_or_build',
                'prompt_template_version', 'runner_version')


def proposal_authoring_fields():
    text = {'$ref': '#/$defs/text'}
    reference = {'anyOf': [reference_schema('REQ'), reference_schema('ISSUE')]}
    change = _object({
        'change_id': {'type': 'string', 'pattern': r'^CHG-[0-7][0-9A-HJKMNP-TV-Z]{25}(?![\s\S])'},
        'targets': _array(text, nonempty=True), 'rationale': text,
        'requirement_or_issue_ids': _array(reference),
        'sources': provenance_schema(), 'assumptions': _array(text),
        'confidence': {'anyOf': [{'type': 'null'},
                                {'type': 'number', 'minimum': 0, 'maximum': 1}]},
    })
    return {'changes': _array(change), **{name: dict(text) for name in MODEL_FIELDS},
            'unknown_reasons': {'type': 'object', 'additionalProperties': text}}


def validate_model_provenance(value):
    """Check declarations, never fill gaps or contact a model/provider."""
    fields = set(MODEL_FIELDS) | {'unknown_reasons'}
    present = fields.intersection(value)
    is_authoring = 'changes' in value or bool(present)
    if not is_authoring:
        return  # Preserve historical passive records without rewriting them.
    if 'changes' not in value:
        raise ModelError('proposal_explanations_required', pointer='/changes')
    if value['created_by']['actor_type'] == 'ai' or present:
        missing = fields - value.keys()
        if missing:
            raise ModelError('proposal_model_fields_required', pointer='/' + sorted(missing)[0])
        unknown = {name for name in MODEL_FIELDS if value[name] == 'unknown'}
        if set(value['unknown_reasons']) != unknown:
            raise ModelError('proposal_unknown_reasons_mismatch', pointer='/unknown_reasons')
