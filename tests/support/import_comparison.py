"""Synthetic mapping projections and histories for the five normative cases."""
from specroad.exchange import ImportComparison
from support.import_identities import history, MAPPING


STRATEGIES = ("error", "skip", "update_if_unchanged", "create_new_revision")
ADOPTING = ("update_if_unchanged", "create_new_revision")
BASE = {"statement": "original", "value": [True, None, 1]}
EXTERNAL = {"statement": "supplier change", "value": [True, None, 1]}
LOCAL = {"statement": "local change", "value": [True, None, 1]}


def imported(**changes):
    arguments = {"imported_projection": BASE, "source_projection": BASE}
    arguments.update(changes)
    return history(**arguments).data


def compare(**changes):
    arguments = {"identity": imported(), "mapping_id": MAPPING,
                 "strategy": "update_if_unchanged", "local_projection": BASE,
                 "source_projection": EXTERNAL}
    arguments.update(changes)
    return ImportComparison(**arguments)
