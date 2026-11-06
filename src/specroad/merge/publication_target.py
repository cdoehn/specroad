"""Independent historical byte reconstruction and fresh native target checks."""
from dataclasses import dataclass
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ..migration.plan_values import unb64, file_bindings, changes
from ..recovery._owned_checks import checked_bytes
from ._recorded import recorded_sources
from .metadata import verify_merge_metadata
from .target import verify_merge_target
from .publication_contract import require


def reconstructed(inputs, source):
    """Owned original proof only. This never observes original filesystem paths."""
    def check():
        sources = recorded_sources(inputs['sources'])
        ours = sources.ours.files
        require(all(source.get(p)==raw for p,raw in ours.items()), 'merge_publication_ours_bytes')
        from ..model.configuration import ProjectConfiguration
        from ..model.paths import CURRENT_JSON_CLASSES, classify_path
        config=ProjectConfiguration(parsed(source['specroad.json']))
        registry=config.data.get('language_registry',{}).get('path')
        normative={p for p in source if classify_path(p,config) in CURRENT_JSON_CLASSES or p==registry}
        require(normative=={p for p in ours if classify_path(p,config) in CURRENT_JSON_CLASSES or p==registry},
            'merge_publication_current_ours_inventory')
        candidate=verify_merge_metadata(unb64(inputs['metadata_bytes_base64']),
            unb64(inputs['plan_bytes_base64']), sources, history=inputs['history'],
            expected_plan_sha256=inputs['plan_sha256'])
        require(candidate.data['metadata_complete'], 'merge_publication_metadata_incomplete')
        result=dict(source)
        for path in ours:
            if path not in candidate.files: result.pop(path)
        for path, raw in candidate.files.items():
            require(path in ours or path not in source or source[path]==raw, 'merge_publication_unowned_collision')
            result[path]=raw
        require(candidate.files['specroad.json']==unb64(inputs['target_configuration']), 'merge_publication_configuration_binding')
        return sources, candidate, tuple(sorted(result.items()))
    sources,candidate,files=checked_bytes('merge-publication-originals', (jcs(inputs),tuple(sorted(source.items()))),check)
    return sources,candidate,dict(files)


def result_artifacts(source, target):
    from ..migration.model_inputs import records
    from ..bundles._payload_model import owned_payload_model
    model=owned_payload_model(target,source_label='merge:publication-target')
    rows=[]
    for item in records(model):
        if item.storage_class!='legacy_immutable' and source.get(item.path)!=target[item.path]:
            value=item.data;rows.append({'artifact':value,'sha256':digest(value)})
    return sorted(rows,key=lambda row:row['artifact']['id'])


def recheck_plan(plan, source):
    op=plan.data['operations'][0];inputs=op['inputs']
    require(file_bindings(source)==op['source_files'], 'merge_publication_source_files')
    sources,candidate,target=reconstructed(inputs,source)
    results=result_artifacts(sources.ours.files,candidate.files)
    require(op['target_files']==file_bindings(target) and op['changes']==changes(source,target)
        and op['source_model_root_sha256']==sources.ours.binding['model_root_sha256']
        and op['target_model_root_sha256']==candidate.data['expected_target_model_root_sha256']
        and plan.data['result_artifacts']==results and op['result_ids']==[r['artifact']['id'] for r in results],
        'merge_publication_native_plan_mismatch')
    return sources,candidate,target


@dataclass(frozen=True)
class PublicationValidation:
    _raw: bytes
    @property
    def data(self): return parsed(self._raw)


def validate_publication_target(plan, source, target, *, services=None):
    from ..recovery._validation import project_validation_report
    from ..recovery._specialists import review_checks
    from ..recovery._evidence_history import evidence_assessments
    from ..recovery.services import native_services
    from ..validation import assess_validation
    from ..verification.code_reference_state import assess_code_reference
    from ..storage.record_artifact import RecordArtifact
    sources,candidate,expected=recheck_plan(plan,source)
    require(target==expected, 'merge_publication_materialized_target')
    inputs=plan.data['operations'][0]['inputs'];services=native_services(services)
    checked=verify_merge_target(unb64(inputs['target_bytes_base64']),
        unb64(inputs['metadata_bytes_base64']),unb64(inputs['plan_bytes_base64']),sources,
        history=inputs['history'],expected_target_sha256=inputs['target_sha256'],
        expected_metadata_sha256=inputs['metadata_sha256'],expected_plan_sha256=inputs['plan_sha256'],services=services)
    require(checked.data['target_validated'] is True, 'merge_publication_target_invalid')
    model,root,report=project_validation_report(candidate.files,services=services)
    assessment=assess_validation(report,fail_on=model.configuration.data['validation_policy'].get('fail_on','error'),documents=model.documents)
    require(assessment.passed and report.complete and report.data['model_valid'] is True
        and root==plan.data['expected_result']['model_root_sha256'], 'merge_publication_target_invalid')
    reviews=review_checks(model)
    code=[]
    for doc in model.documents:
        if parsed(doc.content)['artifact_type']=='code_ref':
            record=RecordArtifact(doc.content,expected_type='code_ref',path=doc.path)
            require(services.code_source is not None,'merge_publication_code_source_required')
            observation=assess_code_reference(services.code_source(model.snapshot(),record),record).data
            require(observation['state']=='current','merge_publication_code_reference_changed')
            code.append(observation)
    return PublicationValidation(jcs({'format_version':'merge-publication-validation-v1',
        'native':report.data,'assessment':assessment.as_dict(),
        'relation_reviews':[row.as_fields() for row in reviews.statuses],
        'evidence':list(evidence_assessments(model)), 'code_references':code}))
