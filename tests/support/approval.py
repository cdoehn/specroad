"""Synthetic reviews/services exercise bindings, never authenticate a real human."""
from specroad.validation import (ApprovalContext, ApprovalPrerequisite, HumanRequirementReview,
    ReviewVerification, ReviewVerifier, assess_requirement_approval)
from specroad.validation.approval_values import HUMAN_CRITERIA, PREREQUISITES
from .domain import domain_value
from .records import record_value
from .model_validation import doc, edge, profile


def values(kind='functional', **changes):
    requirement=domain_value('requirement', maturity='in_review', rationale='Offline auditability.',
                             requirement_kind=kind)
    origin=record_value('source')
    verification=record_value('verification')
    requirement['relations']=[edge(origin,'derived_from',0),edge(verification,'verified_by',1)]
    requirement.update(changes)
    return [requirement,origin,verification]


def context(records=None, **kwargs):
    records=values() if records is None else records
    kwargs.setdefault('profile',profile())
    return ApprovalContext(records[0]['id'],tuple(doc(v) for v in records), **kwargs)


def review_data(ctx, **changes):
    value={'review_id':'human-review-001','input_sha256':ctx.input_sha256,
        'requirement_id':ctx.requirement_id,'requirement_sha256':ctx.requirement_sha256,
        'force_statement_sha256':ctx.force_statement_sha256,
        'reviewer':{'actor_type':'human','actor_id':'test-reviewer'},
        'reviewed_at':'2026-09-24T12:00:00Z','decision':'confirmed',
        'criteria':dict.fromkeys(HUMAN_CRITERIA,True),'compound':False}
    value.update(changes)
    return value


def verifier(authenticated=True,current=True):
    return ReviewVerifier('test-only-trusted-verifier','1',lambda ctx,rev:
        ReviewVerification(ctx.input_sha256,rev.sha256,authenticated,current))


def prerequisites(ctx):
    return tuple(ApprovalPrerequisite(name,ctx.input_sha256,'passed','a'*64) for name in PREREQUISITES)


def assess(ctx=None, **kwargs):
    ctx=context() if ctx is None else ctx
    kwargs.setdefault('review',HumanRequirementReview(review_data(ctx)))
    kwargs.setdefault('verifier',verifier())
    kwargs.setdefault('prerequisites',prerequisites(ctx))
    return assess_requirement_approval(ctx,**kwargs)


def reasons(result):
    return {item['reason'] for item in result.data['findings']}


def quality_records():
    return values('quality',thresholds=[{'property':'response latency','method':'timestamp difference',
                                       'comparison':'lte','target':{'value':5,'unit':'ms'}}])

QUALITY_FIELDS=(tuple('/thresholds/0/'+key for key in ('property','method','comparison','target')),)
