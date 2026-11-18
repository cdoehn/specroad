"""Consumer byte access from native public package-inspection evidence."""
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

from ._files import require
from ._handoff import MAX_BYTES


def _checked_contents(raw, inspection):
    """Read consumer bytes only after native inspection, matching its evidence."""
    require(inspection.package_sha256 == sha256(raw).hexdigest(), 'return_package_changed', 6)
    require(sum(e.size for e in inspection.entries) <= MAX_BYTES, 'return_package_limit')
    with ZipFile(BytesIO(raw)) as archive:
        result = {e.path: archive.read(e.path) for e in inspection.entries}
    require(all(len(result[e.path]) == e.size and sha256(result[e.path]).hexdigest() == e.sha256
                for e in inspection.entries), 'return_inspected_bytes_changed', 6)
    return result
