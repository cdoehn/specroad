"""Portable review repository; no third-party or SpecRoad dependency."""
import os
from pathlib import Path
import stat
import tempfile
from .contracts import MAX_BYTES, MAX_FILES, MAX_TOTAL_BYTES, decode, require, validate_module, validate_review
from .evidence import assess
from .summary import render_summary


def safe_directory(path):
    path = Path(os.path.abspath(path))
    for parent in (*reversed(path.parents), path):
        require(stat.S_ISDIR(parent.lstat().st_mode), 'Linked or missing directory')
    return path


def read_file(path):
    safe_directory(path.parent)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= MAX_BYTES, 'Linked, special or oversized input')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        actual = os.fstat(stream.fileno())
        require(stat.S_ISREG(actual.st_mode) and actual.st_nlink == 1, 'Linked or special opened input')
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (actual.st_dev, actual.st_ino, actual.st_size, actual.st_mtime_ns), 'Input changed while opening')
        raw = stream.read(MAX_BYTES + 1)
        end = os.fstat(stream.fileno())
        require((end.st_size, end.st_mtime_ns, end.st_ctime_ns, end.st_nlink) ==
                (actual.st_size, actual.st_mtime_ns, actual.st_ctime_ns, actual.st_nlink), 'Input changed while reading')
    safe_directory(path.parent)
    require(path.lstat() == end, 'Input changed after reading')
    return decode(raw)


def load_repository(root):
    root = safe_directory(root)
    module_dir = safe_directory(root / 'modules')
    result_dir = safe_directory(root / 'results')
    modules, reviews = {}, {}
    total_bytes = 0
    module_paths = list(module_dir.iterdir())
    require(len(module_paths) <= 100, 'Too many modules')
    for path in sorted(module_paths):
        require(path.suffix == '.json', 'Unexpected module entry')
        module = validate_module(read_file(path))
        require(path.name == module['id'] + '.json' and module['id'] not in modules, 'Module path mismatch')
        modules[module['id']], reviews[module['id']] = module, []
        total_bytes += path.stat().st_size
        require(total_bytes <= MAX_TOTAL_BYTES, 'Review repository too large')
    require(1 <= len(modules) <= 100, 'Invalid module count')
    count = 0
    folders = list(result_dir.iterdir())
    require(len(folders) <= 101, 'Too many result directories')
    for folder in sorted(folders):
        if folder.name == '.gitkeep':
            info = folder.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == 0, 'Invalid placeholder')
            continue
        require(folder.name in modules, 'Unknown result module')
        safe_directory(folder)
        paths = list(folder.iterdir())
        require(count + len(paths) <= MAX_FILES, 'Too many review files')
        for path in sorted(paths):
            count += 1
            require(count <= MAX_FILES and path.suffix == '.json', 'Unexpected or excessive results')
            total_bytes += path.lstat().st_size
            require(total_bytes <= MAX_TOTAL_BYTES, 'Review repository too large')
            review = validate_review(read_file(path))
            require(review['module_id'] == folder.name and path.name == review['id'] + '.json', 'Review path mismatch')
            reviews[folder.name].append(review)
    reports = [assess(module, reviews[key]) for key, module in modules.items()]
    return modules, reports


def publish_summary(root, content):
    root = safe_directory(root)
    destination = root / 'README.md'
    if os.path.lexists(destination):
        info = destination.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'Unsafe summary destination')
    fd, temporary = tempfile.mkstemp(prefix='.summary-', dir=root)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content.encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(root, command):
    modules, reports = load_repository(root)
    if command == 'summary':
        publish_summary(root, render_summary(modules, reports))
    else:
        require(command == 'validate', 'Unknown command')
    return dict(format_version=1, valid=True, modules=[{k: r[k] for k in (
        'module_id', 'module_sha256', 'total', 'accepted', 'open', 'review_coverage_complete', 'release_accepted')} for r in reports])
