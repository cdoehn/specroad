"""Invocation-local bounded metadata phases, not a durable work checkpoint."""
import os

from ..security import SafetyViolation
from ..security.resource_access import opened_resource

MAX_METADATA_BYTES = 1024 * 1024


class MetadataPhases:
    """Count actual input bytes across capture, observation and verification.

    A full phase continues at the current descriptor offset. Separate necessary
    verification passes have distinct read identities; none restarts because a
    phase filled. A later work engine must persist any cross-invocation cursor.
    """

    def __init__(self):
        self._reads = 0
        self._phases = []

    def begin_read(self):
        self._reads += 1
        return self._reads

    @property
    def available(self):
        used = self._phases[-1]['metadata_bytes_read'] if self._phases else 0
        return MAX_METADATA_BYTES - used if used < MAX_METADATA_BYTES else MAX_METADATA_BYTES

    def consume(self, path, read_id, offset, size):
        while size:
            if not self._phases or self._phases[-1]['metadata_bytes_read'] == MAX_METADATA_BYTES:
                self._phases.append({'phase': len(self._phases),
                    'kind': 'metadata_detail' if self._phases else 'short_preflight',
                    'metadata_bytes_read': 0,
                    'first_cursor': {'path': path, 'read_id': read_id, 'offset': offset}})
            phase = self._phases[-1]
            amount = min(size, MAX_METADATA_BYTES - phase['metadata_bytes_read'])
            phase['metadata_bytes_read'] += amount
            offset += amount
            size -= amount
            phase['next_cursor'] = {'path': path, 'read_id': read_id, 'offset': offset}

    def read_bytes(self, boundary, path):
        read_id = self.begin_read()
        chunks, offset = [], 0
        with opened_resource(boundary, path) as (fd, info):
            while offset < info.st_size:
                raw = os.read(fd, min(65536, self.available, info.st_size - offset))
                if not raw:
                    raise SafetyViolation('Metadata content changed during inspection')
                self.consume(path, read_id, offset, len(raw))
                chunks.append(raw)
                offset += len(raw)
            # opened_resource verifies size, timestamps, identity and root again.
        return b''.join(chunks)

    def summary(self):
        return {'metadata_bytes_read': sum(p['metadata_bytes_read'] for p in self._phases),
                'metadata_phase_limit_bytes': MAX_METADATA_BYTES,
                'preflight_detail_required': len(self._phases) > 1,
                'metadata_phases': [{**p, 'first_cursor': dict(p['first_cursor']),
                                     'next_cursor': dict(p['next_cursor'])} for p in self._phases],
                'continuation_scope': 'current_invocation', 'checkpoint_persisted': False}
