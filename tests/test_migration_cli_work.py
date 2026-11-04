"""Actual public Work checkpoints and portable packages; no saved write grant."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
from specroad import _build
from specroad.cli.results import thaw
from support.migration_cli import case,invoke,success,planned,verified
from support.migration_transaction import normative
from support.read_only import inventory,no_write_attempts


@pytest.fixture
def recorded(monkeypatch):
    # Explicit synthetic host build, never a claimed installed/released binary.
    monkeypatch.setattr(_build,'BUILD_METADATA',{'format_version':1,
        'hash_algorithm':'specroad-dev-payload-v1','build_sha256':'4'*64})


def work(command,path,options=None):
    return invoke('work.'+command,options or {},arguments={'work_dir':str(path)})


def finish(path):
    for _ in range(5):
        result=work('resume',path)
        assert result.exit_code in (0,8),result
        if result.exit_code==0:return success(result)['data']
    pytest.fail('Native finite migration phases did not complete')


@pytest.mark.parametrize('phase',range(4))
def test_public_planning_packages_survive_each_checkpoint_and_rebind_fresh_authority(recorded,tmp_path,phase):
    data=case(tmp_path);root=data[0];before=inventory(root);directory=tmp_path/'work'
    result=invoke('migrate.plan',{**data[2],'--work-dir':str(directory)})
    assert result.exit_code==8 and inventory(root)==before
    for _ in range(phase):assert work('resume',directory).exit_code in (0,8)
    overlapping=tmp_path/'work.zip'
    rejected=work('export',directory,{'--output':str(overlapping)})
    assert rejected.exit_code==7 and not overlapping.exists() and inventory(root)==before
    packages=tmp_path/'packages';packages.mkdir()
    package=packages/'work.zip';exported=success(work('export',directory,{'--output':str(package)}))
    assert package.is_file() and exported['operation']=='export'
    shutil.rmtree(directory);new=tmp_path/'restored'
    restored=success(invoke('work.restore',{'--output':str(new)},arguments={'file':str(package)}))
    assert restored['data']['work_dir']==str(new)
    value=finish(new)
    assert value['target_observation']=='planned_target' and not value['project_writes_performed']
    assert inventory(root)==before
    options={'--project':str(root),'--to':'0.2.0','--work-dir':str(new),
        '--expected-plan-sha256':value['planning']['change_plan']['change_plan_sha256'],
        '--expected-inputs-sha256':value['planning']['inputs_sha256'],
        '--backup-root':str(data[-1]),'--backup':'source.zip','--transaction-id':'work-cli'}
    with no_write_attempts():denied=invoke('migrate.apply',options,authorize=False)
    assert denied.exit_code==2 and inventory(root)==before
    applied=success(invoke('migrate.apply',options))
    assert applied['execution']['write_state']=='committed'
    state=inventory(root);replay=success(invoke('migrate.apply',options))
    assert replay['execution']['replayed'] and inventory(root)==state


def test_public_verify_work_is_only_a_provided_target_observation(recorded,tmp_path):
    data=case(tmp_path);_,options=planned(data);applied=success(invoke('migrate.apply',options));root=data[0]
    directory=tmp_path/'verify-work';before=inventory(root)
    options={**options,'--expected-backup-sha256':applied['backup']['file']['sha256'],'--work-dir':str(directory)}
    initial=invoke('migrate.verify',options);assert initial.exit_code==8
    value=finish(directory)
    assert value['target_observation']=='provided_target_bytes'
    assert value['verification']['verified'] and not value['verification']['current_readiness_verified']
    assert inventory(root)==before


def test_public_incomplete_work_cannot_publish_and_preserves_confirmed_prefix(recorded,tmp_path):
    data=case(tmp_path);directory=tmp_path/'work'
    assert invoke('migrate.plan',{**data[2],'--work-dir':str(directory)}).exit_code==8
    before=inventory(data[0]);work_before=inventory(directory)
    options={'--project':str(data[0]),'--to':'0.2.0','--work-dir':str(directory),
        '--expected-plan-sha256':'a'*64,'--expected-inputs-sha256':'b'*64,
        '--backup-root':str(data[-1]),'--backup':'source.zip','--transaction-id':'incomplete'}
    with no_write_attempts():result=invoke('migrate.apply',options)
    assert result.exit_code==6 and result.details['reason']=='migration_work_incomplete'
    assert inventory(data[0])==before and inventory(directory)==work_before


def test_public_resume_in_another_process_uses_stored_bytes_but_no_authority(recorded,tmp_path):
    data=case(tmp_path);directory=tmp_path/'work'
    assert invoke('migrate.plan',{**data[2],'--work-dir':str(directory)}).exit_code==8
    script="""import json,sys
sys.path.insert(0,sys.argv[1])
from specroad import _build
_build.BUILD_METADATA={'format_version':1,'hash_algorithm':'specroad-dev-payload-v1','build_sha256':'4'*64}
from specroad.cli.application import execute_request
from specroad.cli.results import thaw
response=execute_request({'command_id':'work.resume','arguments':{'work_dir':sys.argv[2]}}).result
print(json.dumps({'exit_code':response.exit_code,'result':thaw(response.result)}))
"""
    run=subprocess.run([sys.executable,'-I','-B','-c',script,str(Path(__file__).resolve().parents[1]/'src'),str(directory)],
        cwd=tmp_path,capture_output=True,text=True,timeout=180)
    assert run.returncode==0,run.stderr
    assert json.loads(run.stdout)['exit_code']==8
    value=finish(directory)
    assert value['verification']['verified'] and normative(data[0])==data[1]


def test_cancelled_public_work_cannot_resume_or_authorize_migration(recorded,tmp_path):
    data=case(tmp_path);directory=tmp_path/'work'
    assert invoke('migrate.plan',{**data[2],'--work-dir':str(directory)}).exit_code==8
    before=inventory(data[0]);cancelled=success(work('cancel',directory,{'--reason':'Synthetic cancellation'}))
    assert cancelled['operation']=='cancel'
    assert work('resume',directory).exit_code!=0 and inventory(data[0])==before


def test_public_work_destination_cannot_overlap_project(recorded,tmp_path):
    data=case(tmp_path);before=inventory(data[0])
    with no_write_attempts():
        result=invoke('migrate.plan',{**data[2],'--work-dir':str(data[0]/'work')})
    assert result.exit_code==7 and inventory(data[0])==before


def test_explicit_budget_requests_a_genuine_continuation(recorded,tmp_path):
    data=case(tmp_path);directory=tmp_path/'budget-work'
    initial=invoke('migrate.plan',{**data[2],'--work-dir':str(directory),'--step-wall-ms':'1'})
    assert initial.exit_code==8
    value=finish(directory)
    assert value['verification']['verified'] and normative(data[0])==data[1]
