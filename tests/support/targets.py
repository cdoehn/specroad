"""Synthetic complete supplied projects; no live inventory or approval claims."""
from specroad.changes import (TargetModel, TargetPolicy, prepare_change_plan,
                              prepare_change_lifecycle)
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import artifact_path
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument, ModelGate
from support.model import configuration_value
from support.profiles import profile_data

ACTOR = {'actor_type':'human','actor_id':'planner'}
TIME = '2026-07-01T00:00:00Z'
POLICY = TargetPolicy('ordinary-change','1',())
SCOPE = {'scope_version':'scope-v1','scope_kind':'project','selector':{},
         'configuration_id':None,'closure_profile':'core-closure-v1','boundary_policy':'closed'}


def model(artifacts, *, config=None, profiles=None, resource_files=(), attachments=(), binding=None):
    values = profiles or [profile_data(profile_id='core')]
    resources = [ProfileResource(canonical_json_bytes(p)) for p in values]
    profile = compose_profiles(resources, core_key=resources[0].key,
                               cli_profiles=[r.key for r in resources[1:]])
    return TargetModel(canonical_json_bytes(config or configuration_value()),
        binding or ProjectReadBinding('sample','/explicit/provider', (1,2)),
        [ModelDocument(artifact_path(a['artifact_type'],a['id'],'SR'),canonical_json_bytes(a)) for a in artifacts],
        profile=profile, resource_files=[*(ModelDocument('profiles/'+p.profile_id+'.json',p.source_bytes)
                                          for p in resources), *resource_files], attachments=attachments)


def plan(model, operations, *, preconditions=(), request_id='request-1'):
    folded = prepare_change_lifecycle(model.artifacts,operations,
        metadata_policy_version='change-metadata-v1',actor=ACTOR,planned_at=TIME,
        preconditions=preconditions,source_files=model.source_files)
    target = model.manifest(folded.artifacts,SCOPE)
    return prepare_change_plan({'format_version':'1.2.0','metadata_policy_version':'change-metadata-v1',
        'change_plan_id':'CP-explicit','request_id':request_id,'actor':ACTOR,'planned_at':TIME,
        'base':{'scope_descriptor':SCOPE,'model_root_sha256':model.manifest(model.artifacts,SCOPE).sha256},
        'operations':operations,'preconditions':list(preconditions),
        'result_artifacts':[{'artifact':c.data,'sha256':c.candidate_sha256} for c in folded.candidates],
        'expected_result':{'model_root_sha256':target.sha256}})


def gate(identity='extension:command', check=None, version='1'):
    return ModelGate(identity,version,
        lambda c:c.dependency_result({i:[] for i in c.subjects}),
        check or (lambda c:c.result()))


def resign(p, change):
    data = p.data;data.pop('change_plan_sha256');change(data)
    return prepare_change_plan(data)
