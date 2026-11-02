"""Complete isolated synthetic contracts and compiled transformations.

Expected values come from literal fixture data, never the transformer under test.
The JSON names no executable code and does not register a production provider.
"""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from specroad.migration import (DataContract, MigrationStep, MigrationRegistry,
                                TestVector as Vector, Transformation)
from specroad.model._schema import validate_builtin
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError


def fixture():
    return json.loads((Path(__file__).parents[1] / 'fixtures/migration_graph_v1.json').read_bytes())


def bound(definition, *, specification=None):
    return DataContract(definition['schema_version'],
                        sha256(canonical_json_bytes(definition)).hexdigest(), specification)


def contract(version, *, specification=None):
    """A complete tiny JSON contract for topology-only synthetic cases."""
    return bound({'schema_version': version,
                  'schema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
                  'profile': {'profile_id': 'empty', 'profile_version': '1.0.0'}},
                 specification=specification)


def empty(value):
    return type(value) is dict and not value


def identity_step(source, target, name='identity.v1', *, reversible=False):
    # Even topology-only cases have an actual defined transform and vectors.
    program = Transformation(empty, dict, lambda before, after: empty(before) and empty(after),
                             (Vector('empty', {}, {}),), True)
    return MigrationStep(name, source, target, program, reversible,
                         replace(program, vectors=(Vector('reverse-empty', {}, {}),))
                         if reversible else None)


def chain():
    data = fixture()
    definitions = data['contracts']
    nodes = tuple(bound(d) for d in definitions)

    def accepts(index, value):
        try:
            validate_builtin(value, definitions[index]['schema'])
        except ModelError:
            return False
        return index != 2 or value['title_length'] == len(value['title'])

    def rename(value):
        value['title'] = value.pop('label')
        return value

    def unrename(value):
        value['label'] = value.pop('title')
        return value

    def length(value):
        return {**value, 'title_length': len(value['title'])}

    def unlength(value):
        del value['title_length']
        return value

    def renamed(before, after):
        return (before['id'] == after['id'] and before['tags'] == after['tags']
                and before['label'] == after['title'])

    def extended(before, after):
        return all(before[key] == after[key] for key in ('id', 'title', 'tags'))

    def program(first, last, transform, invariant):
        keys = 'abc'
        vectors = tuple(Vector(row['name'], row[keys[first]], row[keys[last]])
                        for row in data['vectors'])
        return Transformation(lambda value: accepts(first, value), transform,
                              lambda before, after: accepts(last, after) and invariant(before, after),
                              vectors, True)

    first = MigrationStep('rename.v1', nodes[0], nodes[1], program(0, 1, rename, renamed), True,
                          program(1, 0, unrename, lambda a, b: renamed(b, a)))
    second = MigrationStep('length.v1', nodes[1], nodes[2], program(1, 2, length, extended), True,
                           program(2, 1, unlength, lambda a, b: extended(b, a)))
    return MigrationRegistry(nodes, (first, second)), data
