"""Owned artifact-normalization transactions with explicit test host authority."""
from contextlib import contextmanager
from specroad.changes import (prepare_change_target, prepare_publication_check,
    project_lock, begin_building_journal, stage_building_journal)
from specroad.model.representation import NormalizationCandidate
from .publication import prepared as project, options, ALLOW, TRANSACTION
from .targets import ACTOR, TIME, SCOPE, POLICY

FIELDS = dict(change_plan_id='CP-normalize', request_id='format-1', actor=ACTOR,
              planned_at=TIME, scope_descriptor=SCOPE,
              metadata_policy_version='change-metadata-v1')


def operation(document):
    candidate = NormalizationCandidate(document.path, document.content)
    return {'op': 'representation_normalize', 'path': document.path,
            'expected_byte_sha256': candidate.expected_byte_sha256,
            'target_byte_sha256': candidate.result_byte_sha256}


def prepared(root, *, artifacts=None, paths=None):
    model, _, _ = project(root, artifacts=artifacts, operations=[])
    operations = [operation(d) for d in model.documents if paths is None or d.path in paths]
    assessment = prepare_change_target(model, operations, policy=POLICY, **FIELDS)
    check = prepare_publication_check(assessment.plan, model, policy=POLICY)
    return model, assessment.plan, check


@contextmanager
def staged(root, **kwargs):
    model, plan, check = prepared(root, **kwargs)
    with project_lock(root, **options(check)) as held:
        building = begin_building_journal(check, held_lock=held,
            transaction_id=TRANSACTION, authority=ALLOW)
        journal = stage_building_journal(check, building, held_lock=held, authority=ALLOW)
        yield model, plan, check, held, journal
