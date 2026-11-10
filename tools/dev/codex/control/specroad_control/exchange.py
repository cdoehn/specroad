"""Select Result/Patch candidates by native-core-verified identity and binding."""
from pathlib import Path
import stat
import time
import os
from copy import deepcopy
from hashlib import sha256
from .config import Config
from .contracts import timestamp
from .core import Core
from .errors import ControlError
from .hints import hint, signature  # Maintain the public import used by clients.

from .patch_source import BINDING, matches_source


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


class Exchange:
    def __init__(self, config: Config, core: Core, *, observe=None):
        self.config, self.core = config, core
        self.identity = (config.exchange.stat().st_dev, config.exchange.stat().st_ino)
        self.artifacts = ArtifactCache()
        self.cache = self.artifacts.facts
        self.observe = observe or (lambda **values: None)

    def paths(self):
        directory = self.config.exchange
        current = directory.lstat()
        if stat.S_ISLNK(current.st_mode) or (current.st_dev, current.st_ino) != self.identity:
            raise ControlError("exchange_replaced", "The Exchange identity changed.")
        directories = [directory]
        if self.config.archive_directory:
            archive = directory / self.config.archive_directory
            if archive.exists() and not archive.is_symlink() and archive.is_dir():
                directories.append(archive)
        for location in directories:
            for path in sorted(location.iterdir()):
                if ".zip" in path.name and not path.name.startswith(".") and not path.is_symlink():
                    yield path

    def candidates(self, kind: str, predicate):
        started = time.monotonic()
        progress = dict(phase='discovering', kind=kind, visited=0, eligible=0,
                        validated=0, cache_hits=0, current=None, elapsed_seconds=0.0)
        def report(phase, current=None):
            progress.update(phase=phase, current=current, elapsed_seconds=time.monotonic()-started)
            self.observe(validation=dict(progress))
        report('discovering')
        try:
            for path in self.paths():
                progress['visited'] += 1
                try:
                    sig = signature(path)
                    h = self.artifacts.hint(path, sig)
                except (OSError, ValueError):
                    continue
                if progress['visited'] % 50 == 0:
                    report('discovering')
                if not (h and h['kind'] == kind and h['manifest'].get('repo_id') == self.config.repo_id
                        and predicate(h['manifest'])):
                    continue
                progress['eligible'] += 1
                try:
                    sig = signature(path)
                    data = self.artifacts.get(kind, path, sig)
                    if data is None:
                        report('validating', path.name)
                        data = getattr(self.core, kind)(path)
                        if signature(path) != sig:
                            continue
                        self.artifacts.remember(kind, path, sig, data)
                        progress['validated'] += 1
                    else:
                        progress['cache_hits'] += 1
                    if signature(path) != sig:
                        continue
                    if data.get('binding', {}).get('repo_id') == self.config.repo_id:
                        yield data
                except ControlError as exc:
                    if exc.code != 'core_rejected':
                        raise
                except (OSError, ValueError):
                    continue
            report('complete')
        except BaseException:
            report('interrupted')
            raise

    def source(self, source: dict) -> dict:
        # Paths may change through normal PatchHarbor archival, hashes may not.
        found = None
        for candidate in self.candidates("result", lambda m: m.get("run_id") == source["run_id"]):
            if candidate["sha256"] != source["sha256"]:
                raise ControlError("result_identity_conflict", "The same Result run ID has different bytes.")
            found = candidate
        if found is not None:
            return found
        raise ControlError("source_result_missing", "The bound source Result is unavailable.")

    def assert_current(self, source: dict, known_runs: set):
        # Timestamp is only a conservative veto, never a basis for selecting a
        # different source. Actual follow-ups always need patch SHA + binding.
        stamp = timestamp(source.get("captured_at"))
        if stamp is None:
            return
        def suspect(manifest):
            if manifest.get("run_id") in known_runs:
                return False
            try:
                candidate_time = timestamp(manifest.get("created_at"))
                return candidate_time is None or candidate_time >= stamp
            except (ValueError,TypeError):
                return True
        for candidate in self.candidates("result", suspect):
            if candidate["dry_run"] or candidate["run_id"] in known_runs:
                continue
            candidate_time = timestamp(candidate.get("captured_at"))
            if candidate_time is None or candidate_time >= stamp:
                raise ControlError("source_superseded", "A later/ambiguous Result exists outside the claimed chain; review instead of guessing.")

    def patches(self, source: dict) -> list[dict]:
        matched = {}
        for data in self.candidates("patch", lambda m: all(m.get(k) == source["binding"][k] for k in BINDING)):
            checked = self.core.validate(Path(data["path"]), source)
            if matches_source(self, source, checked):
                matched[checked["sha256"]] = checked
        return list(matched.values())

    def following(self, source: dict, patch_sha: str) -> list[dict]:
        found = {}
        by_run = {}
        for data in self.candidates("result", lambda m: m.get("patch_sha256") == patch_sha):
            if data["operation"] != "apply" or data["dry_run"] or data.get("expected") != source["binding"]:
                continue
            if data["run_id"] == source["run_id"]:
                raise ControlError("result_cycle", "A Result cannot follow itself.")
            if data["run_id"] in by_run and by_run[data["run_id"]] != data["sha256"]:
                raise ControlError("result_identity_conflict", "Conflicting bytes for one Result run.")
            by_run[data["run_id"]] = data["sha256"]
            found[data["sha256"]] = data
        return list(found.values())
