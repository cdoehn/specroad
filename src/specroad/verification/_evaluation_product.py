"""Pure product-input manifest and byte observations for an evaluation.

These helpers receive validated, owned input values. A product state contains
only the declared subject identity and actual input manifest: no SpecRoad model
root, run selection, role inventory, audit data or runtime measurements. They do
not discover files, infer a build or grant any verification/scope authority.
"""
from hashlib import sha256

from ..model.canonical import canonical_json_sha256


def input_manifest(owned):
    return [{'logical_path': path, 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
        for path, raw in sorted(owned.items(), key=lambda pair: pair[0].encode('utf-8'))]


def product_state_sha256(subject):
    projection = {key: subject[key] for key in ('subject_id', 'manifest')}
    return canonical_json_sha256(projection)


def observe_input_bytes(subject, owned):
    missing, mismatched, matched = [], [], []
    expected = {entry['logical_path']: entry for entry in subject['manifest']}
    for path, entry in expected.items():
        if path not in owned:
            missing.append(path)
        elif len(owned[path]) != entry['size'] or sha256(owned[path]).hexdigest() != entry['sha256']:
            mismatched.append(path)
        else:
            matched.append(path)
    unexpected = sorted(set(owned) - set(expected), key=lambda path: path.encode('utf-8'))
    return {'matched_inputs': matched, 'missing_inputs': missing,
        'mismatched_inputs': mismatched, 'unexpected_inputs': unexpected,
        'input_bytes_verified': not (missing or mismatched or unexpected)}
