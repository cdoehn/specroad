"""Document semantics and explicit generated outputs over owned model inputs."""
from .roles import DocumentRoleAssessment, DocumentRoleError, assess_document_roles
from .structure import DocumentStructureAssessment, DocumentStructureError, assess_document_structure
from .blocks import ContentBlock, content_block_payload_schema
from .references import ArtifactReferenceError, ArtifactReferenceResolution, resolve_artifact_reference
from .prose import ProseContent, ProseError, parse_prose
from .tables import TableBlockData, TableBlockError, resolve_table_block
from .views import ViewData, ViewError, resolve_view
from .rendering import RenderError, render_document, render_view
from .exports import ViewExportError, export_view, view_export_schema
from ._export_output import write_view_export
from .diagrams import DiagramData, DiagramError, resolve_diagram, render_diagram
from .requirement_presentation import (RequirementPresentation, RequirementPresentationError,
                                       resolve_requirement_presentation)
from .table_presentation import (TablePresentation, resolve_table_presentation,
                                 resolve_view_presentation)
from .builtin_views import (BuiltinViewData, BuiltinViewError, BuiltinViewProviderError,
                            resolve_builtin_view, render_builtin_view)
from .builtin_work import (BuiltinViewWorkInput, prepare_builtin_view_work_input,
                           resume_builtin_view_work_input)
from .type_fallback import resolve_type_fallback, render_type_fallback

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
           'ViewExportError', 'export_view', 'view_export_schema', 'write_view_export',
           'DiagramData', 'DiagramError', 'resolve_diagram', 'render_diagram',
           'RequirementPresentation', 'RequirementPresentationError', 'resolve_requirement_presentation',
           'TablePresentation', 'resolve_table_presentation', 'resolve_view_presentation',
           'BuiltinViewData', 'BuiltinViewError', 'BuiltinViewProviderError',
           'resolve_builtin_view', 'render_builtin_view',
           'BuiltinViewWorkInput', 'prepare_builtin_view_work_input', 'resume_builtin_view_work_input',
           'resolve_type_fallback', 'render_type_fallback',
           'DocumentComposition', 'DocumentIncludeError', 'DocumentIncludeCycleError', 'compose_document']
