"""Verified full-bundle bytes projected into the existing comparison scope."""
from pathlib import Path

from ..bundles.container import BundleContainer
from ..bundles.verification import verify_bundle
from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.paths import CURRENT_JSON_CLASSES, classify_path
from ..security import ProjectBoundary
from ..storage.json_syntax import parse_json_object


def bundle_source(filename, reference, expected_project_id):
    """Read an explicit ZIP, never extract it or supplement its owned payloads."""
    if reference is not None:
        raise ModelError('comparison_source_unavailable')
    path = Path(filename)
    boundary = ProjectBoundary(path.parent)
    raw = boundary.read_bytes(path.name)
    verified = verify_bundle(raw)
    if verified['manifest']['bundle_kind'] != 'project':
        raise ModelError('comparison_full_project_required')
    container = BundleContainer(raw)
    files = container.files
    configuration = ProjectConfiguration(parse_json_object(files['specroad.json']))
    if expected_project_id is not None and configuration.project_id != expected_project_id:
        raise ModelError('project_identity_mismatch')
    # Match the local/Git current-JSON observation, not a full-resource merge.
    # Native verification covers the entire ZIP, including binary payloads and
    # receipts; its bound evidence must not be mistaken for extra diff semantics.
    resources = tuple(sorted((name, content) for name, content in files.items()
                             if classify_path(name, configuration) in CURRENT_JSON_CLASSES))

    def finish():
        if boundary.read_bytes(path.name) != raw:
            raise ModelError('comparison_source_changed')
        return canonical_json_bytes({**verified, 'source_bytes_rechecked': True})

    return configuration, resources, str(boundary.root / path.name), None, finish
