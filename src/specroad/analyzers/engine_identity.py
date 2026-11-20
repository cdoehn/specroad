"""Observed numeric runtime inventories; no project settings, paths or secrets."""
from dataclasses import dataclass
from hashlib import sha256

from ._values import decode, digest, encoded, require
from ._report_values import ENGINE_FACTS, engine_values
from ._text_policy import TEXT_POLICY_VERSION
from .registry import builtin_descriptor
from .requests import analyzer_binding
from .requests import AnalyzerRequest


from ._engine_inventory import numeric_inventory as numeric_inventory


@dataclass(frozen=True)
class EngineIdentity:
    _engine: bytes
    _inventory: bytes

    @property
    def data(self):
        return decode(self._engine)

    @property
    def inventory(self):
        return decode(self._inventory)

    @property
    def sha256(self):
        return sha256(self._engine).hexdigest()

    @property
    def reproducible(self):
        return all(self.data[name]['value'] is not None for name in ENGINE_FACTS)


__all__ = ('numeric_inventory', 'EngineIdentity', 'engine_identity', 'EngineBinding', 'bind_engine')

def engine_identity(engine):
    """Project owned observations into the closed T.4 engine contract."""
    values = dict(adapter_version='1.0.0',
        **{name: dict(value=None, reason='engine_not_loaded') for name in ENGINE_FACTS})
    inventories = dict(runtime=None, numpy=None)
    if engine is not None:
        facts = dict(library_versions=dict(engine.library_versions), model_sha256=engine.model_sha256,
            candidates=list(engine.candidates), candidates_sha256=engine.candidates_sha256,
            preprocessing_version=TEXT_POLICY_VERSION, unicode_version=engine.unicode_version)
        values['adapter_version'] = engine.adapter_version
        values.update({key: dict(value=value, reason=None) for key, value in facts.items()})
        for name in inventories:
            raw = getattr(engine, name + '_inventory')
            inventories[name] = None if raw is None else decode(raw)
            values[('runtime' if name == 'runtime' else 'numpy') + '_fingerprint'] = dict(
                value=None if raw is None else digest(inventories[name]),
                reason='numeric_inventory_unavailable' if raw is None else None)
        if inventories['runtime'] is not None:
            require(inventories['runtime'].get('inventory_version') == 'numeric-runtime-v1'
                    and inventories['runtime'].get('implementation') == engine.python_implementation
                    and inventories['runtime'].get('python_version') == engine.python_version,
                    'analyzer_runtime_inventory_mismatch', exit_code=6)
        if inventories['numpy'] is not None:
            require(inventories['numpy'].get('inventory_version') == 'numpy-runtime-v1'
                    and inventories['numpy'].get('version') == dict(engine.library_versions).get('numpy'),
                    'analyzer_numpy_inventory_mismatch', exit_code=6)
    engine_values(values, analyzer_binding(builtin_descriptor(), ['language_detection']))
    return EngineIdentity(encoded(values), encoded(inventories))


@dataclass(frozen=True)
class EngineBinding:
    _encoded: bytes

    @property
    def data(self):
        return decode(self._encoded)

    def require_current(self, request, engine):
        actual = bind_engine(request, engine)
        require(actual._encoded == self._encoded, 'analyzer_engine_binding_changed', exit_code=6)


def bind_engine(request, engine):
    """A JSON-only continuation binding, never a serialized model or checkpoint."""
    require(type(request) is AnalyzerRequest, 'analyzer_request_required', exit_code=2)
    identity = engine_identity(engine)
    require(identity.reproducible, 'analyzer_engine_identity_unavailable', exit_code=5)
    matches = [entry for entry in request.data['analyzers'] if entry['descriptor'] == builtin_descriptor().data]
    require(len(matches) == 1, 'analyzer_reference_not_requested', exit_code=2)
    return EngineBinding(encoded(dict(binding_version='language-engine-v1', **request.binding,
        analyzer=matches[0], engine_sha256=identity.sha256)))
