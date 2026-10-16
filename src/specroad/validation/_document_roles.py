"""Shared primary-role invariant for already validated source records.

Callers own field/identity validation, scope admission and source ordering.
This pure kernel neither discovers project files nor grants semantic approval.
"""


def _document_roles(sources):
    documents = tuple((path, record) for path, record in sources
                      if record['artifact_type'] == 'document')
    primary = tuple((path, record) for path, record in documents
                    if record['maturity'] != 'retired'
                    and record['document_role'] == 'primary_specification')
    findings = [] if len(primary) == 1 else [{
        'reason': 'document_primary_missing' if not primary else 'document_primary_multiple',
        'path': None, 'pointer': '/document_role', 'artifact_id': None,
        'related_ids': [record['id'] for _, record in primary], 'severity': 'error'}]
    return documents, primary, findings
