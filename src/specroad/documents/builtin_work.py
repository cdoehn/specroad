"""Owned semantic Built-in inputs for the existing content-addressed Work store.

The host saves the original model/product bytes together with ``work_input``.
Resume restores data, not handlers or completed results. Only an explicit native
projection evaluates the view, including every required Release gate. This
adapter does not complete a Work manifest or grant a publication permission.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..changes.target_model import TargetModel, _default_scope
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..planning.readiness import ReleaseReadinessContext
from ..planning.readiness_work import resume_release_readiness_context
from ..storage.json_syntax import parse_json_object
from ..verification.currentness_input import (
    checked_currentness_model, resume_currentness_read_input,
)
from ..verification.read_input import (
    checked_model_input, resume_verification_read_input, VerificationReadBindingConflict,
)
from .builtin_views import BuiltinViewError, BuiltinViewProviderError, resolve_builtin_view


@dataclass(frozen=True, init=False)
class BuiltinViewWorkInput:
    """An inert request binding, not a completed view or readiness decision."""
    _raw: bytes
    _model: object
    _verification: object
    _currentness: object
    _readiness: object

    def __init__(self, *args, **kwargs):
        raise TypeError('Use prepare_builtin_view_work_input')

    @property
    def work_input(self):
        return self._raw

    @property
    def sha256(self):
        return sha256(self._raw).hexdigest()

    @property
    def data(self):
        return parse_json_object(self._raw)

    def resolve(self, *, readiness_gates=(), blocker_reviews=(), blocker_verifier=None):
        """Finish the full native projection, retaining negative/provisional data.

        Host gate implementations and review authentication are supplied here,
        never recovered from the Work request. Missing services remain missing.
        """
        return resolve_builtin_view(self._model, self.data['view_name'],
            verification=self._verification, currentness=self._currentness,
            readiness=self._readiness, readiness_gates=readiness_gates,
            blocker_reviews=blocker_reviews, blocker_verifier=blocker_verifier)

    def __bool__(self):
        raise TypeError('A Work input is not completed work or readiness')


def prepare_builtin_view_work_input(model, view_name, *, verification=None,
                                   currentness=None, readiness=None):
    """Capture full semantic selection without rendering, gates or file I/O."""
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    if type(view_name) is not str or view_name not in (
            'specification', 'traceability', 'verification', 'roadmap'):
        raise BuiltinViewError('builtin_view_not_supported', pointer='/view_name', exit_code=2)
    if verification is not None:
        if view_name not in ('verification', 'traceability'):
            raise BuiltinViewError('builtin_verification_input_not_applicable', pointer='/view_name')
        checked_model_input(model, verification)
    if currentness is not None:
        if view_name not in ('verification', 'traceability'):
            raise BuiltinViewError('builtin_currentness_input_not_applicable', pointer='/view_name')
        checked_currentness_model(model, currentness, verification=verification)
    if view_name == 'verification' and verification is None and currentness is None:
        raise BuiltinViewProviderError(view_name)
    if readiness is not None:
        if view_name != 'roadmap':
            raise BuiltinViewError('builtin_readiness_input_not_applicable', pointer='/view_name')
        if type(readiness) is not ReleaseReadinessContext:
            raise BuiltinViewError('typed_release_readiness_context_required', pointer='/readiness')
        if (readiness._model._sources_sha256 != model._sources_sha256
                or readiness._model.binding != model.binding):
            raise BuiltinViewError('builtin_readiness_binding_mismatch', pointer='/readiness', exit_code=6)
    model = model.snapshot()
    data = {'format_version': 'builtin-view-work-input-v1', 'view_name': view_name,
        'project_id': model.binding.project_id, 'input_sha256': model._sources_sha256,
        'model_root_sha256': model.manifest(model.artifacts, _default_scope()).sha256,
        'verification': None if verification is None else parse_json_object(verification.work_input),
        'currentness': None if currentness is None else parse_json_object(currentness.work_input),
        'readiness': None if readiness is None else parse_json_object(readiness.work_input)}
    value = object.__new__(BuiltinViewWorkInput)
    for name, item in (('_raw', canonical_json_bytes(data)), ('_model', model),
            ('_verification', verification), ('_currentness', currentness), ('_readiness', readiness)):
        object.__setattr__(value, name, item)
    return value


def resume_builtin_view_work_input(model, raw, *, expected_sha256, inputs=None,
        input_roles=None, scope_bindings=None, waiver_reviews=None, waiver_verifier=None,
        code_states=()):
    """Use saved inputs and freshly supplied native observations without I/O.

    No result, callback, wall clock, source locator or implicit current build is
    accepted. The host rebinds physical roots independently; semantic hashes and
    every full descriptor must match the preserved Work input.
    """
    if (type(raw) is not bytes or type(expected_sha256) is not str
            or len(expected_sha256) != 64
            or any(c not in '0123456789abcdef' for c in expected_sha256)):
        raise ModelError('builtin_work_input_binding_required')
    if sha256(raw).hexdigest() != expected_sha256:
        raise VerificationReadBindingConflict('builtin_work_input_changed')
    data = parse_json_object(raw)
    if (set(data) != {'format_version', 'view_name', 'project_id', 'input_sha256',
            'model_root_sha256', 'verification', 'currentness', 'readiness'}
            or data['format_version'] != 'builtin-view-work-input-v1'
            or canonical_json_bytes(data) != raw):
        raise ModelError('builtin_work_input_invalid')
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    model = model.snapshot()
    if (data['project_id'] != model.binding.project_id
            or data['input_sha256'] != model._sources_sha256
            or data['model_root_sha256'] != model.manifest(model.artifacts, _default_scope()).sha256):
        raise VerificationReadBindingConflict('builtin_work_model_changed')
    options = dict(inputs=inputs, input_roles=input_roles, scope_bindings=scope_bindings,
                   waiver_reviews=waiver_reviews, waiver_verifier=waiver_verifier)

    def restore(key, reader, **extra):
        if data[key] is None:
            return None
        if type(data[key]) is not dict:
            raise ModelError('builtin_work_input_invalid')
        content = canonical_json_bytes(data[key])
        return reader(model, content, expected_sha256=sha256(content).hexdigest(), **options, **extra)

    verification = restore('verification', resume_verification_read_input)
    currentness = restore('currentness', resume_currentness_read_input, code_states=code_states)
    readiness = restore('readiness', resume_release_readiness_context)
    restored = prepare_builtin_view_work_input(model, data['view_name'],
        verification=verification, currentness=currentness, readiness=readiness)
    if restored.work_input != raw:
        raise VerificationReadBindingConflict('builtin_work_observation_changed')
    return restored
