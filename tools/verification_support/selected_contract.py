"""Pure selection/observation contracts and report-path checks; no test execution."""
import os
from pathlib import Path, PurePosixPath
import stat


def selected_files(root, names):
    root = Path(root).absolute()
    if type(names) not in (list, tuple):
        raise ValueError("A list of explicit file names is required")
    names = tuple(names)
    if not names or any(type(n) is not str for n in names) or len(set(names)) != len(names):
        raise ValueError("Select distinct test files explicitly")
    for name in names:
        path = PurePosixPath(name)
        if (path.is_absolute() or path.as_posix() != name or len(path.parts) < 2
                or path.parts[0] != "tests" or any(p in (".", "..") for p in path.parts)
                or "\\" in name or "::" in name or not path.name.startswith("test_")
                or not path.name.endswith(".py")):
            raise ValueError("Only explicit repository-relative test files are accepted")
        candidate = root
        for i, part in enumerate(path.parts):
            candidate /= part
            mode = candidate.lstat().st_mode
            if not (stat.S_ISREG(mode) if i == len(path.parts)-1 else stat.S_ISDIR(mode)):
                raise ValueError("Linked/special test paths are not allowed")
    return names


def verify_observation(value, names, expected):
    if type(value) is not dict:
        raise ValueError("Missing selected-run observation")
    ids = value.get("nodeids", [])
    aliases = value.get("nodeid_to_test_id", {})
    outcomes = value.get("test_outcomes", {})
    counts = value.get("worker_test_counts", {})
    if (value.get("observation_format_version") != 1 or value.get("engine") != "pytest"
            or type(ids) is not list or not ids or any(type(n) is not str for n in ids)
            or type(aliases) is not dict or type(outcomes) is not dict or type(counts) is not dict
            or any(type(k) is not str or type(v) is not str or not v for k,v in aliases.items())):
        raise ValueError("Invalid selected-run observation contract")
    if (len(ids) != expected or len(set(ids)) != expected
            or {n.split("::", 1)[0] for n in ids} != set(names)
            or set(aliases) != set(ids) or len(set(aliases.values())) != expected
            or set(outcomes) != set(aliases.values())
            or any(v != "passed" for v in outcomes.values())
            or value.get("suite_passed") is not True or value.get("errors") != []
            or type(value.get("tests_run")) is not int or value["tests_run"] != expected
            or type(value.get("pytest_exit_code")) is not int or value["pytest_exit_code"] != 0
            or not counts or any(type(k) is not str or type(v) is not int or v < 0 for k,v in counts.items())
            or sum(counts.values()) != expected):
        raise ValueError("Incomplete, unexpected or nonpassing selected tests")


def new_report_directory(outdir, root):
    """Refuse source paths, parent traversal and symlinked report ancestors."""
    outdir, root = Path(outdir).absolute(), Path(root).absolute()
    if ".." in outdir.parts:
        raise ValueError("Report path must not contain parent traversal")
    try:
        relative = outdir.relative_to(root)
    except ValueError:
        relative = None
    if relative is not None and (not relative.parts or relative.parts[0] not in ("build", "dist")):
        raise ValueError("Test reports must be outside source inputs")
    for ancestor in reversed(outdir.parents):
        if os.path.lexists(ancestor) and not stat.S_ISDIR(ancestor.lstat().st_mode):
            raise ValueError("Unsafe report ancestor")
    outdir.mkdir(parents=True, exist_ok=False)
    return outdir


