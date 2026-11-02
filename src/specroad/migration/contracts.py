"""Immutable trusted migration definitions; no file loading or code discovery."""
from dataclasses import dataclass
import json
import re

from ..model.canonical import canonical_json_bytes
from ..profiles._contract import SEMVER


class MigrationError(ValueError):
    def __init__(self, reason, *, step_id=None):
        self.reason = reason
        self.step_id = step_id
        super().__init__(reason)


def _version(value):
    if type(value) is not str or len(value) > 128 or SEMVER.fullmatch(value) is None:
        raise MigrationError('invalid_version')
    core, separator, suffix = value.split('+', 1)[0].partition('-')
    pre = tuple((0, int(part)) if part.isdigit() else (1, part)
                for part in suffix.split('.')) if separator else ()
    return (*map(int, core.split('.')), 0 if separator else 1, pre)


def _name(value):
    if type(value) is not str or re.fullmatch(r'[a-z][a-z0-9_.-]{0,127}', value) is None:
        raise MigrationError('invalid_identity')


def _encoded(value):
    if type(value) is not dict:
        raise MigrationError('invalid_value')
    try:
        return canonical_json_bytes(value)
    except (ValueError, TypeError, RecursionError) as error:
        raise MigrationError('invalid_value') from error


@dataclass(frozen=True)
class DataContract:
    schema_version: str
    contract_sha256: str
    specification_version: str | None = None

    def __post_init__(self):
        _version(self.schema_version)
        if (type(self.contract_sha256) is not str
                or re.fullmatch(r'[0-9a-f]{64}', self.contract_sha256) is None):
            raise MigrationError('invalid_contract_binding')
        if self.specification_version is not None:
            _version(self.specification_version)


@dataclass(frozen=True, init=False)
class TestVector:
    name: str
    _before: bytes
    _after: bytes

    def __init__(self, name, before, after):
        _name(name)
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, '_before', _encoded(before))
        object.__setattr__(self, '_after', _encoded(after))

    @property
    def before(self):
        return json.loads(self._before)

    @property
    def after(self):
        return json.loads(self._after)


@dataclass(frozen=True)
class Transformation:
    precondition: object
    transform: object
    postcondition: object
    vectors: tuple[TestVector, ...]
    lossless: bool

    def __post_init__(self):
        if (not all(callable(f) for f in (self.precondition, self.transform, self.postcondition))
                or type(self.lossless) is not bool or type(self.vectors) is not tuple
                or not self.vectors or any(type(v) is not TestVector for v in self.vectors)):
            raise MigrationError('incomplete_transformation')
        names, expected = set(), {}
        for vector in self.vectors:
            if vector.name in names:
                raise MigrationError('duplicate_vector')
            if vector._before in expected and expected[vector._before] != vector._after:
                raise MigrationError('vector_conflict')
            names.add(vector.name)
            expected[vector._before] = vector._after


@dataclass(frozen=True)
class MigrationStep:
    step_id: str
    source: DataContract
    target: DataContract
    forward: Transformation
    reversible: bool
    backward: Transformation | None = None

    def __post_init__(self):
        _name(self.step_id)
        if re.fullmatch(r'[a-z][a-z0-9_.-]*\.v[1-9][0-9]*', self.step_id) is None:
            raise MigrationError('unversioned_step', step_id=self.step_id)
        if (type(self.source) is not DataContract or type(self.target) is not DataContract
                or type(self.forward) is not Transformation or type(self.reversible) is not bool):
            raise MigrationError('invalid_step', step_id=self.step_id)
        if self.reversible:
            if type(self.backward) is not Transformation:
                raise MigrationError('reverse_not_implemented', step_id=self.step_id)
            if not self.backward.lossless:
                raise MigrationError('reverse_not_lossless', step_id=self.step_id)
        elif self.backward is not None:
            raise MigrationError('reversibility_conflict', step_id=self.step_id)


@dataclass(frozen=True)
class ResolvedStep:
    step: MigrationStep
    reverse: bool = False

    def __post_init__(self):
        if type(self.step) is not MigrationStep or type(self.reverse) is not bool:
            raise MigrationError('invalid_step')
        if self.reverse and self.step.backward is None:
            raise MigrationError('reverse_not_implemented', step_id=self.step.step_id)

    @property
    def source(self):
        return self.step.target if self.reverse else self.step.source

    @property
    def target(self):
        return self.step.source if self.reverse else self.step.target

    @property
    def transformation(self):
        return self.step.backward if self.reverse else self.step.forward
