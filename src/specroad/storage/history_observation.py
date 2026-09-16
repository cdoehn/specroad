"""Bind neutral history observations to exact supplied resource bytes.

No disk reads or writes, Git access or source resolution. The caller must bind
HistoryOrigin to actual trusted creation provenance before calling this layer;
user-supplied matching labels are not proof of ancestry. No origin is guessed
from IDs, content hashes, display labels or created_at/created_by.
"""

from hashlib import sha256

from ..model.history_values import HistoryObservation
from ..model.identity_values import artifact_identity
from ..model.relation_identity import relation_identity
from .json_syntax import parse_json_object


def observe_artifact_history(raw, *, origin=None):
    value = parse_json_object(raw)
    return HistoryObservation(artifact_identity(value), sha256(raw).hexdigest(), origin)


def observe_relation_history(raw, *, source, origin=None):
    value = parse_json_object(raw)
    return HistoryObservation(relation_identity(value), sha256(raw).hexdigest(), origin, source)
