"""Read-only formal schema, graph, quality and interface prerequisites."""
import math
from ..model.errors import ModelError
from ..model.domain_schemas import DOMAIN_TYPES, validate_domain_fields
from ..model.record_schemas import RECORD_TYPES, validate_record_fields
from ..model.canonical import canonical_json_bytes
from ..profiles.composition import check_composed_fields
from ..storage.json_syntax import parse_json_object
from ..graph.relations import SourceRelations
from ..graph.references import RelationReferences
from ..graph.hierarchies import validate_hierarchies
from ..graph.symmetry import require_canonical_relations
from ..graph.relation_obligations import RelationObligations
from ..srx.pointers import parse_pointer, resolve_tokens
from ..srx.errors import SrxError
from ..lint import Glossary, LiteralPolicy, lint_literals
from ._approval_findings import _finding

def _read(value, pointer):
    try:
        return resolve_tokens(value, parse_pointer(pointer, rule_id='approval-fields'), rule_id='approval-fields')
    except SrxError as error:
        raise ModelError('approval_pointer_invalid',pointer=pointer) from error


def _nonempty(value):
    return type(value) is str and bool(value.strip())


def _numeric(value):
    return type(value) in (int,float) and (type(value) is int or math.isfinite(value))


def _formal(context):
    issues, records, index = [], [], {}
    candidate = None
    for document in context.documents:
        try:
            data = parse_json_object(document.content, path=document.path)
            if data.get('id') == context.requirement_id:
                if candidate is not None or data.get('artifact_type') != 'requirement':
                    raise ModelError('approval_requirement_missing_or_ambiguous')
                candidate = data
                required_state = 'in_review' if context.data['mode'] == 'transition' else 'approved'
                if data.get('maturity') != required_state:
                    issues.append(_finding(context,'approval_source_maturity_invalid',pointer='/maturity',path=document.path))
                # A detached hypothetical state exercises the approved field rules.
                data = dict(data, maturity='approved')
            kind = data.get('artifact_type')
            if kind in DOMAIN_TYPES: validate_domain_fields(data)
            elif kind in RECORD_TYPES: validate_record_fields(data)
            else: raise ModelError('approval_artifact_type_invalid',pointer='/artifact_type')
            record = SourceRelations(canonical_json_bytes(data),path=document.path)
            if record.identity.id in index: raise ModelError('duplicate_artifact_id',pointer='/id')
            records.append(record);index[record.identity.id]=record
        except ModelError as error:
            issues.append(_finding(context,error.reason,code='SRV002',pointer=error.pointer or '',path=document.path))
    if candidate is None:
        issues.append(_finding(context,'approval_requirement_missing_or_ambiguous'))
        return issues
    if issues:
        return issues  # No successful graph projection over a damaged source set.
    try:
        references=RelationReferences(records)
        require_canonical_relations(references)
        validate_hierarchies(references)
        # Core always requires origin and verified_by; a permissive profile or a
        # verification-plan waiver cannot remove these structural obligations.
        obligations=RelationObligations(records, profile_rules=() if context.profile is None else context.profile.minimum_relation_rules())
        for check in obligations.checks:
            if check.artifact_id==context.requirement_id and not check.satisfied and check.severity=='error':
                code=('SRV031' if check.rule_id=='core:requirement-origin' else 'SRV032'
                      if check.rule_id=='core:requirement-verification' else 'SRV030')
                issues.append(_finding(context,check.rule_id,code=code,pointer='/relations'))
    except ModelError as error:
        issues.append(_finding(context,error.reason,code='SRV021',pointer=error.pointer or '',path=error.path))
    projected=index[context.requirement_id].data
    if context.profile is None:
        issues.append(_finding(context,'approval_profile_unavailable',code='APPROVAL_UNAVAILABLE'))
    else:
        for item in check_composed_fields(context.profile,projected)['diagnostics']:
            issues.append(_finding(context,item['reason'],code='SRV002',pointer=item.get('pointer','')))
    # Plain Core placeholders in actual normative leaves are formal failures.
    # This uses the existing literal engine; it is not semantic language detection.
    fields=[]
    roots=('title','statement','rationale','scope','actor','trigger','preconditions',
           'response','object','timing','thresholds','exceptions','deviation_conditions',
           'deviation_authority')
    stack=[('/'+name,candidate[name]) for name in roots if name in candidate]
    while stack:
        pointer,value=stack.pop()
        if type(value) is str:
            fields.append(pointer)
        elif type(value) is list:
            stack.extend((pointer+'/'+str(i),item) for i,item in enumerate(value))
        elif type(value) is dict:
            stack.extend((pointer+'/'+key.replace('~','~0').replace('/','~1'),item)
                         for key,item in value.items())
    if fields:
        policy=LiteralPolicy.from_value({'format_version':1,'policy_id':'approval:core-placeholders',
            'version':'1.0.0','language':candidate['language'],'fields':sorted(fields),
            'term_ids':[],'placeholders':[],'references':[]})
        report=lint_literals(projected,glossary=Glossary(()),policy=policy)
        for item in report['diagnostics']:
            if item['code']=='SRV033':
                finding=_finding(context,'approval_open_placeholder',code='SRV033',pointer=item['pointer'])
                finding['diagnostic']['location']['character_offset']=item['start']
                issues.append(finding)
    # The current semantic service must still validate configuration and oracles,
    # but an explicitly incompatible local subject list is already observable.
    for relation in projected['relations']:
        if relation['type']=='verified_by':
            target=index.get(relation['target'])
            if (target is not None and target.identity.artifact_type=='verification'
                    and context.requirement_id not in target.data['subjects']):
                issues.append(_finding(context,'approval_verification_subject_mismatch',code='SRV032',
                                       pointer='/relations'))
    kind=candidate['requirement_kind']
    if kind=='quality':
        rows=context.data['quality_fields']
        if not rows: issues.append(_finding(context,'approval_quality_projection_missing',pointer='/thresholds'))
        for row in rows:
            values=[_read(candidate,p) for p in row]
            target=values[3]
            valid_target = _numeric(target) or _nonempty(target) or type(target) is bool or (type(target) is dict and set(target)=={'value','unit'}
                            and _numeric(target['value']) and _nonempty(target['unit']))
            conditions=(_nonempty(values[0]), _nonempty(values[1]),
                type(values[2]) is str and values[2] in ('eq','ne','lt','lte','gt','gte','=','!=','<','<=','>','>='),valid_target)
            for i, valid in enumerate(conditions):
                if not valid: issues.append(_finding(context,('approval_quality_property_missing',
                    'approval_quality_method_missing','approval_quality_comparison_invalid',
                    'approval_quality_target_invalid')[i],pointer=row[i]))
    if kind=='interface':
        fields=context.data['interface_fields']
        if not fields: issues.append(_finding(context,'approval_interface_boundary_missing',pointer='/scope'))
        values=[_read(candidate,p) for p in fields]
        targets=[]
        for p,value in zip(fields,values):
            allowed=('component',) if len(fields)==2 else ('component','interface')
            record=index.get(value) if type(value) is str else None
            if record is None or record.identity.artifact_type not in allowed:
                issues.append(_finding(context,'approval_interface_reference_invalid',code='SRV020',pointer=p))
            else:
                targets.append(record.identity.id)
                if record.identity.artifact_type=='interface':
                    for key in ('source_component','target_component'):
                        target=index.get(record.data[key])
                        if target is None or target.identity.artifact_type!='component':
                            issues.append(_finding(context,'approval_interface_endpoint_missing',code='SRV020',pointer=p))
    return issues
