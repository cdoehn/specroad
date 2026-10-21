"""Shared UTF-8 ordering for required-check identities, independent of selection."""


def _key(row):
    return tuple((row[field] or '').encode('utf-8')
        for field in ('subject_artifact_id', 'contract_id', 'test_id', 'check_id'))
