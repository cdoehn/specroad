"""Independent authored UTF-8 carriers, not production serializer output."""
import json
from .plan_models import PLAN, ENTRY, plan, entry
from .model import configuration_value, put

DERIVED = {'title', 'display_id', 'description', 'implemented', 'parent_id', 'plan_id', 'children'}


def token(number):
    alphabet = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
    result = ''
    for _ in range(26):
        result = alphabet[number % 32] + result
        number //= 32
    return result


def metadata(value):
    return {k: v for k, v in value.items() if k not in DERIVED}


def block(head, value, body='', *, indent=0, fence='```', gap='', encoded=None):
    prefix = ' ' * indent
    kind = 'plan' if value['artifact_type'] == 'implementation_plan' else 'entry'
    text = json.dumps(metadata(value), ensure_ascii=False, indent=2) if encoded is None else encoded
    meta = ''.join(prefix + line + '\n' for line in text.split('\n'))
    # U+2028/U+2029 are body characters, not physical Markdown line breaks.
    content = '\n'.join(prefix + line if line.strip(' \t') else line for line in body.split('\n'))
    return (head + '\n' + gap + prefix + fence + 'specroad-' + kind + '-v1\n' +
            meta + prefix + fence + '\n' + content).encode('utf-8')


def small_source(*, plan_id=PLAN, label='PLAN', title='Implementation', description='Plan prose.\n\n',
                 entry_title='Build feature', entry_body='Commit prose.\n'):
    p = plan(); p.update(id=plan_id, title=title, display_id=label, description=description, children=[ENTRY])
    e = entry(); e.update(title=entry_title, display_id='A', description=entry_body, plan_id=plan_id, parent_id=plan_id)
    raw = block('# [' + label + '] ' + title, p, description) + block('## [ ] [A] ' + entry_title, e, entry_body)
    return raw, p, e


def project(root, files):
    put(root, 'specroad.json', json.dumps(configuration_value(schema_version='0.3.0')).encode())
    for identity, raw in files.items():
        put(root, 'spec/implementation-plans/' + identity + '.md', raw)
    from specroad.storage.project import ProjectSource
    return ProjectSource(root)
