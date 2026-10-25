"""Bind historical imported receipts to the native completed extraction.

Neither a manifest flag nor a copied root is a transfer proof. Original
receipt bytes stay unchanged; no live target or recovery authority follows.
"""
from hashlib import sha256

from ..authoring._bootstrap_io import BootstrapError
from ..changes.receipt_values import ReceiptError
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security.resource_access import opened_resource
from ..storage.archive import validate_portable_archive_paths
from ..storage.json_syntax import parse_json_object
from ._extraction_record import COMPLETED, checked_inventory
from .errors import BundleError
from .manifest import MANIFEST_NAME, check_entries, owned_metadata


def _manifest(raw, project_id):
    value = parse_json_object(raw)
    check_entries(value['entries'])
    metadata = owned_metadata({k: v for k, v in value.items() if k != 'entries'})
    paths = [item['path'] for item in value['entries']]
    validate_portable_archive_paths([MANIFEST_NAME, *paths])
    if (raw != canonical_json_bytes(value) or paths != sorted(set(paths), key=lambda p: p.encode('utf-8'))
            or metadata['bundle_kind'] != 'project' or metadata['project_id'] != project_id):
        raise ReceiptError('imported_receipt_manifest_mismatch', exit_code=6)
    return value


def verify_imported_completion(proof):
    """Extend the existing guarded proof with manifest, bootstrap and inodes."""
    try:
        if proof.active_raw is not None:
            raise ReceiptError('imported_receipt_active_work', exit_code=6)
        manifest_raw = proof.read(MANIFEST_NAME, optional=True)
        if manifest_raw is None:
            raise ReceiptError('completion_project_binding_mismatch', exit_code=6)
        manifest = _manifest(manifest_raw, proof.source.configuration.project_id)
        if manifest['idempotency_scope'] != 'portable':
            raise ReceiptError('imported_receipt_not_portable', exit_code=6)
        raw = proof.read('/'.join((*COMPLETED, 'journal.json')), optional=True)
        if raw is None:
            raise ReceiptError('completion_project_binding_mismatch', exit_code=6)
        inventory = {e['path']: e for e in manifest['entries']}
        inventory[MANIFEST_NAME] = {'size': len(manifest_raw), 'sha256': sha256(manifest_raw).hexdigest()}
        entries, _ = checked_inventory(raw,
            root_identity=list(proof.source.boundary._root_identity),
            stage_identity=list(proof.parents[COMPLETED]), inventory=inventory)
        for path in [MANIFEST_NAME, proof.archive_path, *proof.receipt_paths]:
            raw, identity = proof.records[path]
            expected = entries[path]
            if (expected['identity'] != list(identity) or expected['size'] != len(raw)
                    or expected['sha256'] != sha256(raw).hexdigest()):
                raise ReceiptError('imported_receipt_binding_mismatch', exit_code=6, path=path)
        # Check the native operation/project/request links, not just ZIP hashes.
        from ._receipts import completed_receipts
        completed_receipts({p: proof.records[p][0] for p in [proof.archive_path, *proof.receipt_paths]},
                           proof.source.configuration.project_id)
    except (BootstrapError, BundleError, ModelError, KeyError, TypeError, ValueError) as error:
        if isinstance(error, ReceiptError):
            raise
        raise ReceiptError('imported_receipt_proof_invalid', exit_code=6) from error


def reject_missing_imported_request(source, path):
    """An explicitly transported request cannot become a fresh ID by deletion."""
    try:
        with opened_resource(source.boundary, MANIFEST_NAME, missing_ok=True) as (fd, _):
            if fd is None:
                return
            raw = source.boundary.read_bytes(MANIFEST_NAME)
            manifest = _manifest(raw, source.configuration.project_id)
            if manifest['idempotency_scope'] == 'portable' and path in {e['path'] for e in manifest['entries']}:
                raise ReceiptError('imported_request_receipt_missing', exit_code=6, path=path)
            if source.boundary.read_bytes(MANIFEST_NAME) != raw:
                raise ReceiptError('imported_receipt_manifest_changed', exit_code=6)
    except (BundleError, ModelError, KeyError, TypeError, ValueError) as error:
        if isinstance(error, ReceiptError):
            raise
        raise ReceiptError('imported_receipt_proof_invalid', exit_code=6) from error
