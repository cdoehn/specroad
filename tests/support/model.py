"""Small owned configuration fixtures, not fully initialized release projects."""

import json


def configuration_value(**overrides):
    value = {"schema_version": "0.2.0", "project_id": "sample", "project_name": "Sample",
             "id_prefix": "SR", "default_locale": "de-DE",
             "managed_paths": ["spec", "profiles", "rules", "mappings", "attachments", "archive"],
             "profiles": [], "generated_path": "generated", "validation_policy": {"fail_on": "error"}}
    value.update(overrides)
    return value


def configuration_file(root, **overrides):
    value = configuration_value(**overrides)
    (root / "specroad.json").write_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    return value


def put(root, name, data=b'{}'):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path
