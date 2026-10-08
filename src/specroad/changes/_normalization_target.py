"""Byte-bound current JSON normalization inside the existing target/write pipeline."""
from ..model.errors import ModelError
from ..model.paths import PathClass, CURRENT_JSON_CLASSES, classify_path
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
    originals = model.source_files
    target = {d.path: d.content for d in model.documents}
    resources = {}
    seen, files, changed = set(), [], []
    for index, operation in enumerate(operations):
        pointer = '/operations/' + str(index)
        path = operation['path']
        if path in seen:
            raise TargetError('normalization_duplicate_path', pointer=pointer + '/path')
        seen.add(path)
        kind = classify_path(path, model.configuration)
        if kind not in CURRENT_JSON_CLASSES or path not in originals:
            raise TargetError('normalization_current_source_required', pointer=pointer + '/path')
        if model.language_registry is not None and path == model.configuration.data['language_registry']['path']:
            raise TargetError('normalization_protected_byte_resource', pointer=pointer + '/path')
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
        (target if kind is PathClass.ARTIFACT else resources)[path] = candidate.normalized_bytes
        if candidate.change_required:
            changed.append(path)
        files.append({'path': path, 'expected_byte_sha256': candidate.expected_byte_sha256,
                      'target_byte_sha256': candidate.result_byte_sha256,
                      'value_sha256': candidate.value_sha256})
    documents = tuple(ModelDocument(p, b) for p, b in sorted(target.items()))
    return documents, tuple(ModelDocument(p, b) for p, b in sorted(resources.items())), {
        'files': sorted(files, key=lambda item: item['path']), 'changed_paths': sorted(changed)}
