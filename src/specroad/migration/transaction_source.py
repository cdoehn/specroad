"""Narrow native source admission for the existing migrate-apply writer lock."""
from types import SimpleNamespace
from ..security import ProjectBoundary, SafetyViolation
from ..bundles._extracted_root import require_complete_root
from ..storage.json_syntax import parse_json_object
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from .reference01 import inventory_bytes
from ._backup_source import _observe


class MigrationLockSource:
    def __init__(self, root, *, expected_project_id):
        self.boundary = ProjectBoundary(root)
        self._bundle_origin = require_complete_root(self.boundary)
        self._raw = self.boundary.read_bytes('specroad.json')
        value = parse_json_object(self._raw)
        if value.get('schema_version') == '0.1.0':
            files, observed, check = _observe(root)
            inventory = inventory_bytes({p: b for p, b in files.items() if not p.startswith('.specroad/')})
            actual = inventory.data['project_id']
            check()
        else:
            actual = ProjectConfiguration(value).project_id
        if actual != expected_project_id:
            raise ModelError('migration_lock_project_mismatch')
        self.configuration = SimpleNamespace(project_id=actual)
        self.check_current()

    def check_current(self):
        self.boundary._check_root()
        if require_complete_root(self.boundary) != self._bundle_origin:
            raise SafetyViolation('Extracted project origin changed')
        if self.boundary.read_bytes('specroad.json') != self._raw:
            raise ModelError('migration_lock_source_changed')
