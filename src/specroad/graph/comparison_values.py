"""Owned comparison inputs and result values, independent of all adapters."""
from dataclasses import dataclass
import json
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from .relations import SourceRelations


def _owned(value):
    encoded = canonical_json_bytes(value)
    try:
        return json.loads(encoded)
    except (ValueError, RecursionError) as error:
        raise ModelError('comparison_nesting_not_supported') from error


@dataclass(frozen=True, init=False)
class ComparisonResult:
    """Owned, immutable result data; neither a report renderer nor a JSON Patch."""
    _encoded: bytes

    def __init__(self, value):
        object.__setattr__(self, '_encoded', canonical_json_bytes(_owned(value)))

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)


@dataclass(frozen=True, init=False)
class ComparisonInputs:
    """An explicit artifact set. Absence means removal only from THIS set."""
    project_id: str
    records: tuple

    def __init__(self, project_id, records):
        if type(project_id) is not str or not project_id.strip() or '\0' in project_id:
            raise ModelError('comparison_project_required')
        canonical_json_bytes(project_id)
        if isinstance(records, (str, bytes, dict)):
            raise ModelError('comparison_records_required')
        try:
            records = tuple(records)
        except TypeError as error:
            raise ModelError('comparison_records_required') from error
        seen, prefixes = set(), set()
        for record in records:
            if type(record) is not SourceRelations:
                raise ModelError('source_relations_required')
            if record.identity.id in seen:
                raise ModelError('duplicate_artifact_id')
            if 'project_id' in record.data and record.data['project_id'] != project_id:
                raise ModelError('comparison_project_mismatch')
            seen.add(record.identity.id); prefixes.add(record.identity.id_prefix)
        if len(prefixes) > 1:
            raise ModelError('mixed_project_prefix')
        object.__setattr__(self, 'project_id', project_id)
        object.__setattr__(self, 'records', tuple(sorted(records,
            key=lambda record: record.identity.id.encode('utf-8'))))

    @property
    def fingerprint(self):
        return canonical_json_sha256({'project_id': self.project_id,
            'artifacts': [{'id': r.identity.id, 'sha256': canonical_json_sha256(r.data)}
                          for r in self.records]})


