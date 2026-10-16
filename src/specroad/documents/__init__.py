"""Read-only document semantics over owned model inputs."""
from .roles import DocumentRoleAssessment, DocumentRoleError, assess_document_roles
from .structure import DocumentStructureAssessment, DocumentStructureError, assess_document_structure

__all__ = ['DocumentRoleAssessment', 'DocumentRoleError', 'assess_document_roles',
           'DocumentStructureAssessment', 'DocumentStructureError', 'assess_document_structure']
