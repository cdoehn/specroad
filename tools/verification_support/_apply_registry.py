"""Pure numbered-test registry, migration, selection and receipt contracts."""
from hashlib import sha256
import json
import re

REGISTRY = "verification/apply_test_numbers.json"


def validate_registry(value, current_ids, previous=None):
    if type(value) is not dict:
        raise ValueError("Invalid Apply numbering registry")
    version = value.get("format_version")
    fields = {"format_version", "anchor_commit", "test_ids"}
    if version == 2:
        fields |= {"partition_count", "rotation_anchor_commit"}
    if (set(value) != fields
            or type(version) is not int or version not in (1, 2)
            or type(value["anchor_commit"]) is not str
            or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value["anchor_commit"]) is None):
        raise ValueError("Invalid Apply numbering registry")
    if version == 2 and (type(value["partition_count"]) is not int or value["partition_count"] != 3
            or type(value["rotation_anchor_commit"]) is not str
            or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value["rotation_anchor_commit"]) is None):
        raise ValueError("Invalid three-group Apply rotation")
    ids = value["test_ids"]
    if (type(ids) is not list or not ids or any(type(i) is not str or not i for i in ids)
            or len(set(ids)) != len(ids) or not set(current_ids) <= set(ids)):
        raise ValueError("Missing or duplicate stable test numbers")
    if previous is None:
        if ids != sorted(current_ids):
            raise ValueError("Initial numbering must cover the sorted complete collection")
    else:
        validate_registry_shape(previous)
        old = previous["test_ids"]
        additions = ids[len(old):]
        current_additions = set(current_ids) - set(old)
        # A failed N=3 attempt can already have assigned an appended block.
        # A correction appends further IDs; globally sorting both blocks
        # would renumber the first. Preserve the supplied order and require
        # exactly the collected additions, with the full old prefix intact.
        # Initial numbering and the historical/migration contracts stay strict.
        additions_match = (set(additions) == current_additions
            if version == previous["format_version"] == 2
            else additions == sorted(current_additions))
        if (value["anchor_commit"] != previous["anchor_commit"] or ids[:len(old)] != old
                or not additions_match):
            raise ValueError("Existing test numbers must not change or be reused")
        if previous["format_version"] == 2 and (version != 2
                or value["rotation_anchor_commit"] != previous["rotation_anchor_commit"]
                or value["partition_count"] != previous["partition_count"]):
            raise ValueError("Committed Apply rotation must not change or restart")
    return {name: number for number, name in enumerate(ids)}


def validate_registry_shape(value):
    # A historical registry may contain retired IDs; its old initial ordering
    # is no longer a constraint after additional tests have been appended.
    if type(value) is not dict or type(value.get("test_ids")) is not list:
        raise ValueError("Invalid historical numbering registry")
    ordered = dict(value, test_ids=sorted(value["test_ids"]))
    validate_registry(ordered, ordered["test_ids"])


def select_partition(pairs, registry, sequence, previous=None):
    if (type(pairs) is not dict or not pairs or type(sequence) is not int or sequence < 0
            or any(type(n) is not str or not n.startswith("tests/") or "::" not in n
                   or "\n" in n or "\r" in n for n in pairs)
            or any(type(i) is not str for i in pairs.values())
            or len(set(pairs.values())) != len(pairs)):
        raise ValueError("Invalid collected identities or commit sequence")
    numbers = validate_registry(registry, pairs.values(), previous)
    if registry["format_version"] == 2 and (previous is None or previous["format_version"] == 1) and sequence:
        raise ValueError("The first three-group commit must use group zero")
    count = registry.get("partition_count", 2)
    selected = {n: i for n, i in sorted(pairs.items()) if numbers[i] % count == sequence % count}
    if not selected:
        raise ValueError("An empty Apply partition cannot pass")
    return selected


def partition_metadata(registry, sequence):
    """Versioned partial-run identity; legacy evidence retains its old contract."""
    if registry["format_version"] == 1:
        return {"format_version": 1, "purpose": "alternating_apply_tests",
                "test_scope": "stable_even_odd_partition", "parity": "even" if sequence % 2 == 0 else "odd"}
    return {"format_version": 2, "purpose": "rotating_apply_tests",
            "test_scope": "stable_modulo_partition", "partition_count": 3,
            "partition_index": sequence % 3, "rotation_anchor_commit": registry["rotation_anchor_commit"]}


def selection_receipt(registry, raw, selected, head, sequence, runtime_filter=None, required_tests=None, host_resources=None, host_pool=None):
    """Bind the actual numbered selection, without claiming a full-suite run."""
    numbers = {identity: number for number, identity in enumerate(registry["test_ids"])}
    binding = {"format_version": 1, "kind": "apply-selection-binding-v1",
        "base_commit": head, "numbering_anchor_commit": registry["anchor_commit"],
        "rotation_anchor_commit": registry["rotation_anchor_commit"],
        "registry_sha256": sha256(raw).hexdigest(), "commit_sequence": sequence,
        "partition_count": registry["partition_count"], "partition_index": sequence % registry["partition_count"],
        "tests": [{"nodeid": node, "test_id": identity, "test_number": numbers[identity]}
                  for node, identity in sorted(selected.items())]}
    if runtime_filter is not None:
        version = 3 if runtime_filter.get('format_version') == 2 else 2
        binding.update(format_version=version, kind="apply-selection-binding-v" + str(version), runtime_filter=runtime_filter)
    if required_tests is not None:
        if runtime_filter is None or runtime_filter.get('format_version') != 2:
            raise ValueError('Required tests need the current durable runtime snapshot')
        binding.update(format_version=4, kind='apply-selection-binding-v4', required_tests=required_tests)
    if host_resources is not None:
        from .host_execution import validate_resources
        validate_resources(host_resources)
        binding.update(format_version=5, kind="apply-selection-binding-v5", host_resources=host_resources)
    if host_pool is not None:
        if host_resources is None or required_tests is None:
            raise ValueError('Host pools require a complete Apply test/resource contract')
        binding.update(format_version=6, kind='apply-selection-binding-v6', host_pool=host_pool)
    encoded = json.dumps(binding, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode()
    return {"selection_binding": binding, "selection_sha256": sha256(encoded).hexdigest()}
