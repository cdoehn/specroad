"""Byte-bound artifact normalization inside the existing target/write pipeline.

This first writer slice accepts normalization-only plans for current generic
artifacts. Resource/configuration writes and mixed semantic operations remain
explicitly unsupported; no partial target or alternate write path is returned.
"""
from ..model.errors import ModelError
from ..model.paths import PathClass, classify_path
from ..model.representation import NormalizationCandidate
from ..storage.representation import _validate_format_input
from ..validation import ModelDocument
from .target_values import TargetError


def normalization_mode(operations):
    selected = [op['op'] == 'representation_normalize' for op in operations]
    if any(selected) and not all(selected):
        raise TargetError('normalization_mixed_operations_unsupported', pointer='/operations')
    return any(selected)


def normalization_documents(model, operations):
    originals = {d.path: d.content for d in model.documents}
    target = dict(originals)
    seen, files, changed = set(), [], []
    for index, operation in enumerate(operations):
        pointer = '/operations/' + str(index)
        path = operation['path']
        if path in seen:
            raise TargetError('normalization_duplicate_path', pointer=pointer + '/path')
        seen.add(path)
        kind = classify_path(path, model.configuration)
        if kind is not PathClass.ARTIFACT or path not in originals:
            raise TargetError('normalization_artifact_source_required', pointer=pointer + '/path')
        try:
            _validate_format_input(model.configuration, path, originals[path], kind)
            candidate = NormalizationCandidate(path, originals[path])
        except ModelError as error:
            raise TargetError(error.reason, pointer=pointer + error.pointer) from error
        if operation['expected_byte_sha256'] != candidate.expected_byte_sha256:
            raise TargetError('normalization_source_hash_mismatch',
                              pointer=pointer + '/expected_byte_sha256')
        if operation['target_byte_sha256'] != candidate.result_byte_sha256:
            raise TargetError('normalization_target_hash_mismatch',
                              pointer=pointer + '/target_byte_sha256')
        target[path] = candidate.normalized_bytes
        if candidate.change_required:
            changed.append(path)
        files.append({'path': path, 'expected_byte_sha256': candidate.expected_byte_sha256,
                      'target_byte_sha256': candidate.result_byte_sha256,
                      'value_sha256': candidate.value_sha256})
    documents = tuple(ModelDocument(p, b) for p, b in sorted(target.items()))
    return documents, {'files': sorted(files, key=lambda item: item['path']),
                       'changed_paths': sorted(changed)}
