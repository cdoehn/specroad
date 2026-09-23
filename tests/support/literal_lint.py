"""Explicit glossary/policy fixtures, not linguistic judgments or live inventories."""
from .domain import domain_value
from .artifacts import artifact_bytes
from specroad.storage.domain_artifact import DomainArtifact
from specroad.lint import Glossary, LiteralPolicy, lint_literals


def term(number=1, **changes):
    value = domain_value("term", id="SR-TERM-" + str(number).zfill(4), id_scheme="legacy-sequential-v1")
    value.update(changes)
    return DomainArtifact(artifact_bytes(value), expected_type="term")


def policy_data(**changes):
    value = {"format_version": 1, "policy_id": "test:literal", "version": "1.0.0",
        "language": "de-DE", "fields": ["/statement"], "term_ids": ["SR-TERM-0001"],
        "placeholders": ["OFFEN"], "references": []}
    value.update(changes)
    return value


def observe(statement="Controller works.", *, terms=None, policy=None, **changes):
    return lint_literals(domain_value("requirement", statement=statement, **changes),
        glossary=Glossary([term()] if terms is None else terms),
        policy=LiteralPolicy.from_value(policy_data() if policy is None else policy))
