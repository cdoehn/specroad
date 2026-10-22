"""Owned external identity values and explicit, independent import history.

Projection hashes are computed only from caller-supplied values. This layer
provides no native-owner lookup, conflict policy or publication authority.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..graph._relation_validation import EXTERNAL_KEY, _external_identities
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ._identity_errors import ImportIdentityError, _error


@dataclass(frozen=True, init=False)
class ExternalIdentity:
    """The existing native relation identity contract, also usable on artifacts.

    Legacy identities without history remain unbound. Stored hashes and mapping
    names are retained as data; loading them does not verify their provenance.
    """
    _encoded: bytes

    def __init__(self, value):
        try:
            encoded = canonical_json_bytes(value)
            data = parse_json_object(encoded)
            _external_identities([data])
        except ModelError as error:
            raise _error(error, strip="/external_identities/0") from error
        object.__setattr__(self, "_encoded", encoded)

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def key(self):
        data = self.data
        return tuple(data[name] for name in EXTERNAL_KEY)

    @property
    def import_bound(self):
        return "mapping_id" in self.data

    def with_import_history(self, *, mapping_id, imported_projection,
                            source_projection, source_payload, imported_at):
        """Return a candidate with hashes of the explicitly supplied values.

        Projection hashes use JCS; the payload hash uses the exact original
        bytes. No projection is inferred from a complete artifact or from this
        identity. Existing revision and extension values remain unchanged.
        """
        if type(source_payload) is not bytes:
            raise ImportIdentityError("source_payload_bytes_required", pointer="/source_payload")
        hashes = {}
        for name, projection in (("imported_projection", imported_projection),
                                 ("source_projection", source_projection)):
            if type(projection) is not dict:
                raise ImportIdentityError("import_projection_object_required", pointer="/" + name)
            try:
                hashes[name] = sha256(canonical_json_bytes(projection)).hexdigest()
            except ModelError as error:
                raise _error(error, prefix="/" + name) from error
        data = self.data
        data.update(mapping_id=mapping_id, imported_at=imported_at,
                    last_imported_projection_sha256=hashes["imported_projection"],
                    last_source_projection_sha256=hashes["source_projection"],
                    last_source_payload_sha256=sha256(source_payload).hexdigest())
        return ExternalIdentity(data)
