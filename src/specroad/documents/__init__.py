"""Read-only document semantics over owned model inputs."""
from .roles import DocumentRoleAssessment, DocumentRoleError, assess_document_roles

__all__ = ['DocumentRoleAssessment', 'DocumentRoleError', 'assess_document_roles']
