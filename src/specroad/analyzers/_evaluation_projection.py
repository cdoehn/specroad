"""Explicitly structural differences, outside normative Evidence and approvals."""
from ._values import digest, encoded

def disagreements(rows):
    """Expose structural differences without guessing adapter semantics or voting."""
    groups = {}
    for index, row in enumerate(rows):
        report = row['report']
        if report is None:
            continue
        for subject in report['subjects']:
            key = subject['subject_key']
            findings = [{k:v for k,v in f.items() if k != 'finding_id'}
                        for f in report['findings'] if key in f['subject_keys']]
            projection = dict(status=subject['status'], payload=subject['payload'],
                              findings=sorted(findings, key=encoded))
            for capability in report['analyzer']['capabilities']:
                groups.setdefault((key, capability), []).append(dict(
                    report_index=index, run_id=report['run_id'], analyzer=report['analyzer'],
                    engine=report['engine'], observation=projection, observation_sha256=digest(projection)))
    return [dict(code='analyzer_disagreement', comparison='structural_subject_observation',
                 subject_key=key, capability=capability, variants=variants)
            for (key, capability), variants in sorted(groups.items())
            if len({v['observation_sha256'] for v in variants}) > 1]
