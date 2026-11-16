"""Read and validate only independently bound native bootstrap inventory.

This module performs no publication or cleanup. Original package bytes select
the complete expected tree; journals bind actual file identities, not authority.
"""
from hashlib import sha256
import os

from ..authoring._bootstrap_io import BootstrapError, directory, identity, metadata
from ..authoring.bootstrap_completion import _read
from ..bundles._extraction_record import COMPLETED as PROJECT_COMPLETED, checked_inventory
from ..bundles.extraction import _directories
from ..bundles.manifest import MANIFEST_NAME

COMPLETED = ('.specroad', 'recovery', 'sandbox-bootstrap')
FORMAT = 'specroad-ai-sandbox-bootstrap-v1'
PROJECT_RECORD = '/'.join((*PROJECT_COMPLETED, 'journal.json'))


def _require(condition):
    if not condition:
        raise BootstrapError('sandbox_bootstrap_inventory_invalid')

def _project_content(container):
    return {**container.files, MANIFEST_NAME: container.manifest_bytes}

def _project_inventory(parent, container):
    """Admit the actual native extraction record, never a copied marker."""
    content = _project_content(container)
    directories = _directories(content)
    with directory(parent, ('project',)) as project:
        project_info = os.fstat(project)
        with directory(project, PROJECT_COMPLETED) as receipt:
            receipt_info = os.fstat(receipt)
            limit = 4096 + sum(1024 + 2 * len(p.encode('utf-8')) for p in set(content) | directories)
            raw, _ = _read(receipt, 'journal.json', limit)
        expected = {p: {'size': len(b), 'sha256': sha256(b).hexdigest()} for p, b in content.items()}
        native, _ = checked_inventory(raw, root_identity=identity(project_info),
            stage_identity=identity(receipt_info), inventory=expected)
        content[PROJECT_RECORD] = raw
        directories.add('/'.join(PROJECT_COMPLETED))
        captured = {}
        for path in sorted(set(content) | directories):
            parts = path.split('/')
            with directory(project, parts[:-1]) as fd:
                if path in directories:
                    with directory(fd, (parts[-1],)) as child:
                        value = metadata(os.fstat(child))
                else:
                    observed, value = _read(fd, parts[-1], len(content[path]))
                    _require(observed == content[path])
            if path in native:
                _require(value == native[path])
            captured['project/' + path] = value
        captured['project'] = metadata(project_info)
    return content, directories, captured
