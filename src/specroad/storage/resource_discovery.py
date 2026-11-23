"""Inventory discovery shared by readers; callers check ProjectSource freshness.

No generated, operational or archive traversal, and no silent partial result on
an interrupted enumeration. No graph closure, cache or output publication.
"""

from ..model.errors import ModelError
from ..model.paths import CURRENT_JSON_CLASSES, PathClass, project_path
from ..security.resource_access import directory_entries, resource_is_directory


def _current_paths(source, *, include_plans):
    """Enumerate only the configured portions of normative JSON trees."""
    classes = (*CURRENT_JSON_CLASSES, PathClass.PLAN) if include_plans else CURRENT_JSON_CLASSES
    pending = []
    for path in source.configuration.managed_paths:
        if path.split("/")[0] in {"spec", "profiles", "rules", "mappings"}:
            pending.append((path, True))
    seen = set()
    paths = {"specroad.json"}
    while pending:
        path, optional = pending.pop()
        path = project_path(path)
        if path in seen:
            continue
        seen.add(path)
        # A directory can have a .json suffix; classification never guesses.
        is_directory = resource_is_directory(
            source.boundary, path,
            missing_ok=optional and source.classify(path) not in classes,
        )
        if is_directory is None:
            continue
        if not is_directory:
            if source.classify(path) not in classes:
                raise ModelError("unclassified_normative_resource", path=path)
            paths.add(path)
            continue
        # The directory was just observed. Disappearance is no longer an
        # optional missing tree: it invalidates this inventory attempt.
        entries = directory_entries(source.boundary, path)
        for name, is_directory in entries:
            child = project_path(path + "/" + name)
            if is_directory:
                pending.append((child, False))
            elif child.startswith("spec/implementation-plans/"):
                source.classify(child)
                if not include_plans:
                    raise ModelError("plan_markdown_reader_required", path=child)
                paths.add(child)
            elif child.endswith(".json"):
                if source.classify(child) not in classes:
                    raise ModelError("unclassified_normative_json", path=child)
                paths.add(child)
    if len({path.casefold() for path in paths}) != len(paths):
        raise ModelError("resource_path_collision")
    return tuple(sorted(paths))




def current_json_paths(source):
    """Existing JSON consumers must never silently omit a Markdown model."""
    return _current_paths(source, include_plans=False)


def current_model_paths(source):
    """Configured normative carriers, including each plan source exactly once."""
    return _current_paths(source, include_plans=True)
