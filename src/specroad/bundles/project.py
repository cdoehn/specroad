"""Prepare a closed project from actual native bytes, without publishing files.

Completed receipt history is observed and validated separately from the model.
An explicit exclusion declares local_only even for an observed empty history.
Extraction, arbitrary-bundle verification and write admission remain separate.
"""
from .. import __version__
from ..cli.results import OperationFailure
from ..model._bundle_scope_contract import PROJECT
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..srx.errors import SrxError
from ._project_snapshot import ProjectBundleSnapshot
from .container import BundleContainer, encode_bundle
from .errors import BundleError
from .manifest import require


def _metadata(snapshot, exclude_operational_receipts):
    model, descriptor, native = snapshot.model, snapshot.descriptor, snapshot.native
    archives, payloads = snapshot.archives, snapshot.payloads
    exclusions = {p: 'unreferenced_archive_object' for p in archives if p not in payloads}
    if exclude_operational_receipts:
        exclusions.update({p: 'operational_receipts_excluded' for p in snapshot.receipts.payloads})
    return {
        'bundle_format_version': '1.0.0', **PROJECT.creation_fields(),
        'idempotency_scope': 'local_only' if exclude_operational_receipts else 'portable',
        'project_id': model.configuration.project_id, 'schema_version': '0.2.0',
        'tool_version': __version__, 'scope_descriptor': descriptor.data,
        'origin_model_root_sha256': native.sha256, 'bundle_model_root_sha256': native.sha256,
        'profile_sha256': native.data['profile_sha256'],
        'configuration_sha256': native.data['configuration_sha256'],
        'boundary_references': [],
        'excluded_contents': [{'path': p, 'reason': exclusions[p]}
                              for p in sorted(exclusions, key=lambda p: p.encode('utf-8'))],
    }


def _prepare(root, *, exclude_operational_receipts=False):
    if type(exclude_operational_receipts) is not bool:
        raise BundleError('bundle_receipt_exclusion_boolean_required', code=None, exit_code=2)
    snapshot = ProjectBundleSnapshot(root)
    metadata = _metadata(snapshot, exclude_operational_receipts)
    payloads = {**snapshot.payloads, **({} if exclude_operational_receipts else snapshot.receipts.payloads)}
    container = BundleContainer(encode_bundle(metadata, payloads))
    # Compare the decoded product with the complete selected input, not merely
    # an internally consistent ZIP inventory. In particular inactive resources
    # and declarative language-package source bytes must not disappear.
    require(container.files == payloads, 'bundle_project_payload_incomplete', code='SRV060')
    require({key: container.manifest[key] for key in metadata} == metadata,
            'bundle_project_metadata_changed', code='SRV060')
    snapshot.verify_current()
    # Retain the original snapshot until the publisher's final atomic move.
    return container, snapshot.source, snapshot.verify_current


def prepare_project_bundle(root, *, exclude_operational_receipts=False):
    """Return owned canonical bytes after native project selection and closure.

    All current artifact/resource bytes and required snapshot/attachment bytes
    are retained. Profile selection comes from the project; configuration-filtered
    and partial sources are not promoted. No lock, journal, cache or output is
    created. Final rereads detect observed changes, not an atomic disk snapshot.
    The returned container does not grant authenticity, approval or write access.
    """
    try:
        return _prepare(root, exclude_operational_receipts=exclude_operational_receipts)[0]
    except SafetyViolation as error:
        raise BundleError('unsafe_bundle_project_source', code='SRV083', exit_code=7) from error
    except ModelError as error:
        raise BundleError(error.reason, exit_code=getattr(error, 'exit_code', 3)) from error
    except SrxError as error:
        raise BundleError(error.reason, code=error.code) from error
    except OperationFailure as error:
        raise BundleError('bundle_project_preflight_failed', code=None, exit_code=int(error.kind)) from error
    except OSError as error:
        raise BundleError('bundle_project_io', code=None, exit_code=5) from error
