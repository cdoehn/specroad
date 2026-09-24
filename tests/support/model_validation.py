"""Synthetic loaded documents and real narrow predicates for pipeline tests.

These providers test dispatch/coverage, not production evidence authentication.
"""
from specroad.validation import ModelDocument, ModelGate
from specroad.profiles.values import ProfileResource
from specroad.profiles.composition import compose_profiles
from .artifacts import artifact_bytes
from .domain import domain_value, relation
from .profiles import profile_data


def artifact(kind="goal", number=0, **changes):
    value = domain_value(kind)
    prefix = value["id"].rsplit("-", 1)[0]
    value["id"] = prefix + "-" + str(number).zfill(26)
    value.update(changes)
    return value


def doc(value, path=None):
    return ModelDocument(path or value["id"] + ".json", artifact_bytes(value))


def edge(target, kind="supersedes", number=0):
    value = relation(kind, target["id"] if type(target) is dict else target)
    value["relation_id"] = "REL-" + str(number).zfill(26)
    return value


def profile(**overrides):
    value = profile_data(profile_id="core", **overrides)
    return compose_profiles([ProfileResource(artifact_bytes(value))], core_key="core@0.2.0")


def no_dependencies(context):
    # Explicitly observe every input rather than returning an unbound Boolean.
    return context.dependency_result({identity: [] for identity in context.subjects})


def title_gate(name="extension:titles", dependencies=no_dependencies):
    def check(context):
        return context.result([{"reason":"invalid_title", "severity":"error", "artifact_id":identity}
            for identity in context.subjects if context.artifact(identity)["title"] == "forbidden"])
    return ModelGate(name, "1", dependencies, check)
