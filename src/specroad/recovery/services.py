"""Explicit host inputs for the existing native Restore qualification kernels.

These Python values are not a registry, persisted proof format or authority.
Neither project nor plan/Work data can select a provider. Providers return
the actual typed native inputs; the recovery adapter performs the checks.
"""
from dataclasses import dataclass, field
from typing import Callable

from ..model.errors import ModelError
from ..validation.approval_values import (
    ApprovalContext, ApprovalPrerequisite, HumanRequirementReview, ReviewVerifier,
)


@dataclass(frozen=True)
class RequirementReviewInputs:
    context: ApprovalContext
    review: HumanRequirementReview
    verifier: ReviewVerifier
    prerequisites: tuple

    def __post_init__(self):
        if (type(self.context) is not ApprovalContext
                or type(self.review) is not HumanRequirementReview
                or type(self.verifier) is not ReviewVerifier
                or type(self.prerequisites) is not tuple
                or any(type(p) is not ApprovalPrerequisite for p in self.prerequisites)):
            raise ModelError('restore_native_approval_inputs_required')


@dataclass(frozen=True)
class RestoreServices:
    """Current invocation's trusted native input providers, never success gates.

    requirement_review(model, id) returns RequirementReviewInputs, task_done
    returns native TaskImplementation values, and code_source(model, record)
    returns an explicit native ProjectBoundary or GitObjectSource. No provider
    result or external verifier observation is cached by this adapter.
    """
    requirement_review: Callable | None = field(default=None, repr=False)
    task_done: Callable | None = field(default=None, repr=False)
    code_source: Callable | None = field(default=None, repr=False)
    source_content: Callable | None = field(default=None, repr=False)
    proposal_inputs: Callable | None = field(default=None, repr=False)

    def __post_init__(self):
        if any(value is not None and not callable(value) for value in
               (self.requirement_review, self.task_done, self.code_source, self.source_content,
                self.proposal_inputs)):
            raise ModelError('restore_native_services_required')


def native_services(value):
    if value is not None and type(value) is not RestoreServices:
        raise ModelError('restore_native_services_required')
    return RestoreServices() if value is None else value
