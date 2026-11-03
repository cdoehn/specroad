"""Passive exact-Result candidate selection; no ledger or authority changes."""
from pathlib import Path
import zipfile
import zlib
from .errors import ControlError

BINDING = ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm")


def matches_source(exchange, source, patch):
    try:
        return _typed_source_match(exchange, source, patch)
    except ControlError:
        raise
    except (OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError):
        raise ControlError('patch_source_unproven', 'Native source selection evidence is unavailable or malformed.') from None


def _typed_source_match(exchange, source, patch):
    """A typed plan binds exact Result bytes in addition to repository state."""
    from .apply_reconcile_proof import archive_bytes, plan
    try:
        data, _ = plan(patch)
    except (ControlError, ValueError, TypeError, KeyError, IndexError, SyntaxError,
            RecursionError, zipfile.BadZipFile, zlib.error, RuntimeError,
            NotImplementedError, OverflowError):
        # Opaque/legacy packages cannot be excluded by an unproven hint.
        # Recheck the native hash even when parsing cannot establish v2.
        archive_bytes(patch)
        return True
    if data['format_version'] != 2:
        return True
    bound = source
    if data['source_result_sha256'] != source['sha256']:
        candidates = {r['sha256']: r for r in exchange.candidates('result',
            lambda m: all(m.get(k) == source['binding'][k] for k in BINDING))
            if r['sha256'] == data['source_result_sha256']}
        if len(candidates) != 1:
            raise ControlError('patch_source_unproven', 'The exact typed source Result is unavailable.')
        bound = exchange.source(next(iter(candidates.values())))
    if (data['binding'] != patch['binding'] or data['binding'] != bound['binding']
            or data['apply_repository'] != bound['repository_path']
            or bound['repository_path'] != source['repository_path']
            or data['initial_dirty'] != bound['dirty'] or bound['dry_run']):
        raise ControlError('patch_source_unproven', 'Typed source metadata contradicts native evidence.')
    checked = exchange.core.validate(Path(patch['path']), bound)
    if (checked['sha256'] != patch['sha256'] or checked['binding'] != bound['binding']
            or checked['reference_sha256'] != bound['sha256'] or not checked['binding_matches']):
        raise ControlError('patch_source_unproven', 'The typed patch changed during selection.')
    return data['source_result_sha256'] == source['sha256']
