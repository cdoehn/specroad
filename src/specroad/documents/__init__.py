"""Read-only document semantics over owned model inputs."""
from .roles import DocumentRoleAssessment, DocumentRoleError, assess_document_roles
from .structure import DocumentStructureAssessment, DocumentStructureError, assess_document_structure
from .blocks import ContentBlock, content_block_payload_schema
from .references import ArtifactReferenceError, ArtifactReferenceResolution, resolve_artifact_reference
from .prose import ProseContent, ProseError, parse_prose
from .tables import TableBlockData, TableBlockError, resolve_table_block
from .views import ViewData, ViewError, resolve_view
from .rendering import RenderError, render_document, render_view

from .includes import (DocumentComposition, DocumentIncludeError, DocumentIncludeCycleError,
                       compose_document)

__all__ = ['DocumentRoleAssessment', 'DocumentRoleError', 'assess_document_roles',
           'DocumentStructureAssessment', 'DocumentStructureError', 'assess_document_structure',
           'ContentBlock', 'content_block_payload_schema',
           'ArtifactReferenceError', 'ArtifactReferenceResolution', 'resolve_artifact_reference',
           'ProseContent', 'ProseError', 'parse_prose',
           'TableBlockData', 'TableBlockError', 'resolve_table_block',
           'ViewData', 'ViewError', 'resolve_view',
           'RenderError', 'render_document', 'render_view',
           'DocumentComposition', 'DocumentIncludeError', 'DocumentIncludeCycleError', 'compose_document']
