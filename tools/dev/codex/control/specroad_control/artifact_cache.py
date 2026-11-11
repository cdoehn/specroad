"""Bounded reuse of native artifact facts, separate from package selection."""
import os
from copy import deepcopy
import stat
from hashlib import sha256
from .hints import hint, signature


class ArtifactCache:
    """Bounded discovery hints and native facts; never cache a live Apply check."""
    def __init__(self):
        self.facts = {}
        self.hints = {}
        self.content = {}

    @staticmethod
    def store(mapping, key, value, limit):
        mapping.pop(key, None)
        if len(mapping) >= limit:
            mapping.pop(next(iter(mapping)))
        mapping[key] = value

    def hint(self, path, sig):
        key = (str(path), sig)
        if key not in self.hints:
            value = hint(path)
            if signature(path) != sig:
                return None
            if value is not None:
                # Keep only discovery metadata, never thousands of complete
                # base/untracked file inventories from native Result manifests.
                keys = ('marker', 'format_version', 'repo_id', 'base_commit', 'state_fingerprint',
                        'fingerprint_algorithm', 'run_id', 'created_at', 'patch_sha256')
                value = dict(value, manifest={k: value['manifest'][k] for k in keys if k in value['manifest']})
            self.store(self.hints, key, value, 4096)
        return self.hints[key]

    def digest(self, path, sig):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            actual = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            if not stat.S_ISREG(info.st_mode) or actual != sig:
                raise ValueError('Artifact changed before hashing')
            value = sha256(); remaining = sig[2]
            while remaining:
                block = stream.read(min(1024*1024, remaining))
                if not block: raise ValueError('Incomplete artifact')
                value.update(block); remaining -= len(block)
            if stream.read(1) or signature(path) != sig:
                raise ValueError('Artifact changed while hashing')
        return value.hexdigest()

    def get(self, kind, path, sig):
        key = (kind, str(path), sig)
        if key in self.facts:
            if signature(path) != sig:
                raise ValueError('Cached artifact changed')
            return deepcopy(self.facts[key])
        if self.content:
            digest = self.digest(path, sig)
            value = self.content.get((kind, digest))
            if value is not None:
                result = dict(deepcopy(value), path=str(path))
                self.store(self.facts, key, result, 256)
                return deepcopy(result)
        return None

    def remember(self, kind, path, sig, data):
        if signature(path) != sig or self.digest(path, sig) != data['sha256']:
            raise ValueError('Native artifact bytes changed')
        data = deepcopy(data)
        self.store(self.facts, (kind, str(path), sig), data, 256)
        self.store(self.content, (kind, data['sha256']), data, 256)
