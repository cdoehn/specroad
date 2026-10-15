"""Pure applicability classification before scope closure; no discovery or writes."""
from hashlib import sha256

from .models import EffectiveConfiguration
from ..graph.relations import SourceRelations
from ..model.artifact_schemas import artifact_common_schema
from ..model.errors import ModelError
from ..srx import EvaluationContext, SrxError, SrxProgram, evaluate, require_type
from ..srx.graph_validation import GRAPH_OPERATORS
from ..srx.operators import QUANTIFIER_OPERATORS, UNARY_OPERATORS
from ..srx.pointers import parse_pointer


def _check_access(program, metadata_fields):
    pending = [(program.expression, '/expression')]
    while pending:
        node, at = pending.pop()
        op = node['op']
        if op in GRAPH_OPERATORS:
            raise SrxError('applicability_graph_forbidden', rule_id=program.rule_id,
                           pointer=at + '/op', expected='configuration or constant metadata',
                           actual='graph_operation')
        if op == 'field':
            context = node['context']
            if context not in ('artifact', 'configuration', 'item'):
                raise SrxError('applicability_context_forbidden', rule_id=program.rule_id,
                               pointer=at + '/context', expected='configuration or constant metadata',
                               actual='context')
            tokens = parse_pointer(node['pointer'], rule_id=program.rule_id, at=at + '/pointer')
            allowed = metadata_fields if context == 'artifact' else ('configuration_id', 'effective_values')
            if context != 'item' and tokens and tokens[0] not in allowed:
                raise SrxError('applicability_field_forbidden', rule_id=program.rule_id,
                               pointer=at + '/pointer', expected='declared constant metadata field',
                               actual='field')
        elif op in QUANTIFIER_OPERATORS:
            pending.extend(((node['where'], at + '/where'), (node['array'], at + '/array')))
        elif op in UNARY_OPERATORS:
            pending.append((node['arg'], at + '/arg'))
        elif op != 'literal':
            pending.extend((arg, at + '/args/' + str(index))
                           for index, arg in reversed(list(enumerate(node['args']))))


def classify_applicability(record, configuration=None, *, require_configuration=False):
    if type(record) is not SourceRelations:
        raise ModelError('applicability_source_required')
    source = SourceRelations(record.source_bytes, path=record.path)
    if type(require_configuration) is not bool:
        raise ModelError('configuration_requirement_boolean_required', path=source.path)
    if configuration is not None and type(configuration) is not EffectiveConfiguration:
        raise ModelError('effective_configuration_required', path=source.path)
    if require_configuration and configuration is None:
        raise ModelError('configuration_required', path=source.path)
    if (configuration is not None
            and configuration.configuration_id.split('-', 1)[0] != source.identity.id_prefix):
        raise ModelError('configuration_project_mismatch', path=source.path)
    data = source.data
    if 'applicability' not in data:
        status, reason = 'applicable', 'unconditional'
    else:
        if source.identity.artifact_type == 'configuration':
            raise ModelError('configuration_applicability_forbidden', path=source.path,
                             pointer='/applicability')
        metadata_fields = set(artifact_common_schema(source.identity.artifact_type)['properties'])
        metadata_fields.difference_update(('relations', 'applicability'))
        rule_id = 'applicability:' + source.identity.id
        try:
            program = SrxProgram(data['applicability'], rule_id=rule_id)
            _check_access(program, metadata_fields)
            if configuration is None:
                status, reason = 'potentially_applicable', 'no_configuration'
            else:
                roots = {'artifact': {key: value for key, value in data.items() if key in metadata_fields},
                         'configuration': {'configuration_id': configuration.configuration_id,
                                           'effective_values': configuration.effective_values},
                         'project': {}, 'relations': []}
                value = require_type(evaluate(program, EvaluationContext(roots, rule_id=rule_id)),
                                     ('boolean',), rule_id=rule_id)
                status, reason = (('applicable', 'condition_true') if value
                                  else ('excluded', 'condition_false'))
        except SrxError as error:
            raise ModelError('invalid_applicability', path=source.path,
                             pointer='/applicability' + error.pointer) from error
    return {'artifact_id': source.identity.id, 'status': status, 'reason': reason,
            'configuration_id': None if configuration is None else configuration.configuration_id,
            'configuration_sha256': None if configuration is None else configuration.sha256,
            'source_sha256': sha256(source.source_bytes).hexdigest()}
