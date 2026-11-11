"""One target-key vocabulary for workers and both handover paths."""
from hashlib import sha256


def targets(config, paths, *, thread_only=False):
    keys = ["thread-" + sha256((str(config.codex_home.resolve()) + config.session_id).encode()).hexdigest(),
            "thread-id-" + sha256(config.session_id.encode()).hexdigest()]
    if not thread_only:
        keys.extend(["repo-" + sha256(str(config.repository.resolve()).encode()).hexdigest(),
                     "apply-" + sha256(config.repo_id.encode()).hexdigest(),
                     "apply-path-" + sha256(str(config.apply_directory.resolve()).encode()).hexdigest()])
    return sorted({root / (key + ".lock") for root in paths.lock_roots for key in keys})
