"""Owned synthetic registries for corruption/project-binding tests, not IANA."""
from hashlib import sha256
from specroad.model.language_registry import LanguageRegistry
from specroad.storage.language_registry import registry_binding
from .model import configuration_file, put


def registry_bytes(*records, version="2020-01-01"):
    records = records or (("language", "en"), ("region", "US"))
    chunks = ["File-Date: " + version]
    for kind, value in records:
        field = "Tag" if kind in {"grandfathered", "redundant"} else "Subtag"
        chunks.append("Type: " + kind + "\n" + field + ": " + value
                      + "\nDescription: Synthetic test record\nAdded: 2005-10-16")
    return ("\n%%\n".join(chunks) + "\n").encode()


def load_registry(raw=None, version="2020-01-01"):
    raw = registry_bytes() if raw is None else raw
    return LanguageRegistry(raw, expected_sha256=sha256(raw).hexdigest(), expected_version=version)


def project_registry(root, raw=None):
    registry = load_registry(raw)
    binding = registry_binding(registry)
    configuration_file(root, language_registry=binding)
    put(root, binding["path"], registry.source_bytes)
    return binding
