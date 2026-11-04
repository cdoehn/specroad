"""Owned synthetic sources and fixed independent Q.3 expected values."""
import json
from pathlib import Path
from .migration_plans import vector_source
from .reference01 import put, relation, seal

REQUIREMENT = 'spec/requirements/SR-REQ-0001.json'
VECTORS = json.loads((Path(__file__).resolve().parents[1] /
    'data/migration_relation_vectors.json').read_text())['vectors']
EXPECTED = {row['name']: row['relation_id'] for row in VECTORS}


def pair_source():
    files = vector_source()
    goal = json.loads(files['spec/goals/SR-GOAL-0001.json'])
    goal['id'] = 'SR-GOAL-0002'; put(files, goal)
    source = json.loads(files[REQUIREMENT])
    source['relations'].append(relation('addresses', goal['id'])); put(files, source)
    return files


def immutable_source():
    files = vector_source()
    # A synthetic sealed baseline is immutable. Its relation has a legal
    # symmetric owner (BASE sorts before REQ), not an invented human review.
    seal(files, relations=[relation('conflicts_with', 'SR-REQ-0001')])
    return files
