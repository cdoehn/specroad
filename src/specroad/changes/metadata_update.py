"""Shared physical update stamp after native guards and lifecycle decisions.

Callers supply validated original audit values, an explicit bound actor/time
and a genuinely changed final candidate. This helper does not decide change,
content revision, authoring rights or publication. It never reads a clock.
"""
from ..model.audit_values import Revision
from .metadata_time import next_update_time


def updated_audit_fields(before, *, actor, planned_at):
    return {
        'revision': Revision(before['revision']).value + 1,
        'created_at': before['created_at'],
        'created_by': before['created_by'],
        'updated_at': next_update_time(planned_at, before['updated_at']),
        'updated_by': actor,
    }
