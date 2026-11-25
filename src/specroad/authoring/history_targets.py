"""Passive identity inputs from complete, recorded native byte targets."""
from base64 import b64decode
from binascii import Error as Base64Error
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object


def values(operation):
    rows = []
    if operation.get('op') == 'resource_replace':
        target = operation.get('target')
        if type(target) is dict:
            rows.append((operation.get('path'), target.get('bytes_base64'), True))
    elif operation.get('op') in ('schema_migrate', 'merge_publish'):
        changes = operation.get('changes')
        for row in changes if type(changes) is list else ():
            if type(row) is dict:
                rows.append((row.get('path'), row.get('after_bytes_base64'), True))
    elif operation.get('op') == 'plan_edit':
        sources = operation.get('sources')
        for row in sources if type(sources) is list else ():
            if type(row) is dict:
                rows.extend((row.get('path'), row.get(side), False) for side in ('before', 'after'))
    for path, text, encoded in rows:
        if type(path) is not str or type(text) is not str:
            continue
        try:
            raw = b64decode(text, validate=True) if encoded else text.encode('utf-8')
            if path.endswith('.json'):
                yield parse_json_object(raw)
            elif path.endswith('.md'):
                from ..storage.plan_markdown import parse_plan
                yield [p.data for p in parse_plan(raw, path=path).projections]
        except (ModelError, Base64Error, UnicodeError, ValueError):
            # Arbitrary or invalid original bytes provide no native identity.
            # Their validation finding remains in the immutable Force report.
            continue
