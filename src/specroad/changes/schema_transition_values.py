"""Closed schema-transition records in the common transaction namespaces."""
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from .values import ChangePlan
from .execution_values import ChangeExecutionError
from ._journal_codec import _transaction, _hash, _target_path
from .receipt_values import transaction_receipt_path, request_receipt_path, RequestReceipt
from .authoring import normalize_authoring_actor, normalize_request_id
from ._authoring_policy import select_route
from ..migration.plan_values import b64, unb64

FORMAT = 'schema-transition-journal-v1'
FORMATS = (FORMAT,'merge-transition-journal-v1')


class SchemaTransitionError(ChangeExecutionError):
    def __init__(self, reason, *, exit_code=6, write_state='unknown'):
        super().__init__(reason, exit_code=exit_code, write_state=write_state)


def require(ok, reason, *, exit_code=6):
    if not ok:
        raise SchemaTransitionError(reason, exit_code=exit_code)


def authoring(plan):
    data = plan.data
    actor = normalize_authoring_actor(data['actor'])
    identity = normalize_request_id(data['request_id'])
    from ._snapshot_dispatch import command_for
    route = select_route(command_for(plan), actor, identity, False, False)
    require(route == 'direct', 'migration_direct_authoring_required', exit_code=7)
    return digest(data['operations'])


@dataclass(frozen=True, init=False)
class TransitionJournal:
    _raw: bytes
    _plan: ChangePlan = field(repr=False, compare=False)

    def __init__(self, raw):
        require(type(raw) is bytes, 'transition_journal_bytes_required')
        value = parsed(raw)
        fields = {'format_version', 'state', 'transaction_id', 'project_id', 'root_identity',
            'request_id', 'plan_bytes_base64', 'plan_sha256', 'backup', 'source_modes', 'published_count', 'images_prepared', 'validation'}
        require(set(value) == fields and value['format_version'] in FORMATS, 'transition_journal_schema')
        _transaction(value['transaction_id'])
        plan = ChangePlan(unb64(value['plan_bytes_base64']))
        require(plan.data['metadata_policy_version'] in ('migration-metadata-v1','merge-metadata-v1') and plan.sha256 == value['plan_sha256'],
                'transition_plan_binding')
        from ._snapshot_dispatch import format_for, is_merge
        require(value['format_version']==format_for(plan),'transition_format_policy_binding')
        authoring(plan)
        require(value['request_id'] == plan.data['request_id'], 'transition_request_binding')
        op = plan.data['operations'][0]
        from ..model.configuration import ProjectConfiguration
        config = ProjectConfiguration(parsed(unb64(op['inputs']['target_configuration']))).data
        registry_path = config.get('language_registry', {}).get('path')
        for row in op['changes']:
            if row['path'] == registry_path:
                from ..migration.plan_values import safe_path
                safe_path(row['path'])
            else:
                _target_path(row['path'])
        identity = value['root_identity']
        require(type(identity) is list and len(identity) == 2 and all(type(v) is int and v >= 0 for v in identity),
                'transition_root_identity')
        config = parsed(unb64(op['inputs']['target_configuration']))
        require(value['project_id'] == config['project_id'], 'transition_project_binding')
        backup = value['backup']
        require(type(backup) is dict and set(backup) == {'path', 'output_root', 'size', 'sha256', 'source_files_sha256'}
            and type(backup['size']) is int and backup['size'] > 0
            and _hash(backup['sha256']) and backup['source_files_sha256'] == digest(op['source_files'])
            and all(type(backup[k]) is str and str(Path(backup[k])) == backup[k]
                    and Path(backup[k]).is_absolute() and '..' not in Path(backup[k]).parts
                    for k in ('path', 'output_root'))
            and Path(backup['path']).is_relative_to(backup['output_root']), 'transition_backup_binding')
        modes = value['source_modes']
        require(type(modes) is dict and set(modes) == {r['path'] for r in op['source_files']}
                and all(type(v) is int and 0 <= v <= 0o777 for v in modes.values()), 'transition_mode_binding')
        prepared = value['images_prepared']
        require(type(prepared) is bool, 'transition_preparation_flag')
        states = ('building', 'prepared', 'committing', 'committed', 'rolling_back', 'rolled_back')
        state, count = value['state'], value['published_count']
        require(state in states and type(count) is int and 0 <= count <= len(op['changes']), 'transition_state')
        require(state not in ('building', 'prepared', 'rolled_back') or count == 0, 'transition_state')
        require(prepared or count == 0 and state in ('building','rolling_back','rolled_back'), 'transition_images_unprepared')
        require(state != 'building' or not prepared, 'transition_images_unprepared')
        require(state != 'committed' or count == len(op['changes']), 'transition_state')
        report = value['validation']
        if is_merge(plan):
            require(type(report) is dict and set(report)=={'format_version','native','assessment','relation_reviews','evidence','code_references'}
                and report['format_version']=='merge-publication-validation-v1'
                and all(type(report[k]) is list for k in ('relation_reviews','evidence','code_references')),
                'merge_transition_validation_schema')
            report=report['native']
        require(type(report) is dict and report.get('format_version') == 'model-validation-v1'
            and report.get('checks_complete') is True and report.get('model_valid') is True
            and report.get('structural_scope') == 'all_supplied_documents', 'transition_validation_incomplete')
        expected = [{'path': r['path'], 'sha256': r['sha256']} for r in op['target_files']
                    if r['path'].startswith('spec/') and r['path'].endswith('.json')]
        require(report.get('source_bindings') == expected, 'transition_validation_binding')
        require(raw == jcs(value), 'transition_noncanonical_journal')
        object.__setattr__(self, '_raw', raw)
        # This is the already validated immutable value owned by these exact
        # journal bytes, never a cached live-state or authorization decision.
        object.__setattr__(self, '_plan', plan)

    @property
    def data(self): return parsed(self._raw)
    @property
    def source_bytes(self): return self._raw
    @property
    def sha256(self): return sha256(self._raw).hexdigest()
    @property
    def plan(self): return self._plan
    @property
    def path(self): return '.specroad/transactions/' + self.data['transaction_id'] + '/journal.json'
    @property
    def receipt_root(self): return transaction_receipt_path(self.data['transaction_id']).rsplit('/', 1)[0]
    def successor(self, state, count):
        return TransitionJournal(jcs({**self.data, 'state': state, 'published_count': count,
            'images_prepared': state in ('prepared','committing','committed') or
                self.data['images_prepared'] and state != 'building'}))
    def __bool__(self): raise TypeError('A journal is not a completed transaction')


def transaction_receipt(journal):
    require(journal.data['state'] == 'committed', 'transition_not_committed')
    plan = journal.plan.data; op = plan['operations'][0]
    from ._snapshot_dispatch import is_merge
    return jcs({'format_version': 'merge-transition-receipt-v1' if is_merge(journal.plan) else 'schema-transition-receipt-v1', 'journal_sha256': journal.sha256,
        'transaction_id': journal.data['transaction_id'], 'plan_sha256': journal.plan.sha256,
        'source_files_sha256': digest(op['source_files']), 'target_files_sha256': digest(op['target_files']),
        'target_model_root_sha256': op['target_model_root_sha256'], 'validation_sha256': digest(journal.data['validation'])})


def result_object(journal):
    value, plan = journal.data, journal.plan.data
    return {'exit_code': 0, 'status': 'success', 'write_state': 'committed',
        'transaction_id': value['transaction_id'], 'request_id': plan['request_id'],
        'target_model_root_sha256': plan['expected_result']['model_root_sha256'],
        'published_paths': sorted(r['path'] for r in plan['operations'][0]['changes']), 'created_ids': []}


def request_receipt(journal):
    data, plan = journal.data, journal.plan.data
    if plan['request_id'] is None:
        return None
    from ._snapshot_dispatch import is_merge
    raw = jcs({'format_version': 'merge-transition-request-receipt-v1' if is_merge(journal.plan) else 'schema-transition-request-receipt-v1', 'namespace': 'normative_write',
        'request_id': plan['request_id'], 'project_id': data['project_id'],
        'transaction_id': data['transaction_id'], 'actor': plan['actor'],
        'operations_sha256': digest(plan['operations']),
        'base_model_root_sha256': plan['base']['model_root_sha256'],
        'target_model_root_sha256': plan['expected_result']['model_root_sha256'],
        'result': 'committed', 'created_ids': [], 'result_object': result_object(journal),
        'transaction_receipt': {'path': transaction_receipt_path(data['transaction_id']),
                                'sha256': sha256(transaction_receipt(journal)).hexdigest()}})
    return RequestReceipt(raw)


@dataclass(frozen=True, init=False)
class TransitionRequest:
    _raw: bytes
    @classmethod
    def from_journal(cls, journal):
        result = object.__new__(cls)
        from ._snapshot_dispatch import command_for
        data = {'command_id': command_for(journal.plan), 'plan': journal.plan.data, 'plan_sha256': journal.plan.sha256,
            'backup': journal.data['backup'], 'root_identity': journal.data['root_identity'],
            'project_id': journal.data['project_id'], 'transaction_id': journal.data['transaction_id'],
            'validation': journal.data['validation'], 'write_authorized': False, 'approval_granted': False}
        object.__setattr__(result, '_raw', jcs(data)); return result
    @property
    def data(self): return parsed(self._raw)
    @property
    def sha256(self): return sha256(self._raw).hexdigest()
    @property
    def plan(self): return ChangePlan(jcs(self.data['plan']))
