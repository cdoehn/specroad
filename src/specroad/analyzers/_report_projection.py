"""Independent semantic observation, provenance and operational views."""
RESULT_FIELDS = ('contract_version', 'report_version', 'snapshot_sha256', 'analyzer',
                 'engine', 'subjects', 'coverage', 'run_status', 'findings', 'extensions')


def observation(value):
    return {key:value[key] for key in RESULT_FIELDS}

def provenance(value):
    return {key:value[key] for key in ('analyzer', 'engine')}

def operational(value):
    return value['operational']
