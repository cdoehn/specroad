"""Shared actual authoring and lossless recipient preparation for 19.x."""
from hashlib import sha256
import json
import pytest
from specroad.authoring.creation import create_artifact
from specroad.authoring.inputs import normalize_artifact_create_input
from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.identities import IdentityInventory
from test_artifact_creation import project, arguments
from test_authoring_inputs import fields
from test_language_packages import MINIMUM
from test_requirement_exchange_right import TEXTS

CONTENT = ('language','normative_force','statement')


@pytest.fixture(scope='module')
def authored(tmp_path_factory):
    root=tmp_path_factory.mktemp('multilingual-authoring')/'project'
    project(root)
    values=[]
    for index,language in enumerate(MINIMUM):
        native=InspectionSnapshot(root,None).model
        ids=IdentityInventory('SR',[v['id'] for v in native.artifacts],(),())
        data=fields('requirement')
        force=('must','must_not','should','may')[index%4]
        data.update(language=language,normative_force=force,statement=TEXTS[language]+
            '\r\nExact: Café / Cafe\u0301 / 👩\u200d💻 / "<&>". **must should may soll** remain original data.')
        if force=='should':data.update(deviation_conditions='Only the explicit exception.',deviation_authority='Named project role.')
        options=arguments(native,ids)
        options.update(change_plan_id='CP-roundtrip-'+str(index),transaction_id='txn-roundtrip-'+str(index),request_id='roundtrip-'+str(index))
        created=create_artifact(native,normalize_artifact_create_input('requirement',data),**options)
        assert created['write_state']=='committed' and created['completion']['current_target_verified']
        value=json.loads((root/created['path']).read_bytes())
        assert {key:value[key] for key in CONTENT}=={key:data[key] for key in CONTENT}
        values.append(value)
    return root,tuple(values)


def meaning_hashes(values):
    return {v['id']:dict(record=sha256(jcs(v)).hexdigest(),
        **{key:sha256(jcs(v[key])).hexdigest() for key in CONTENT}) for v in values}


def install_owned_files(root, files):
    # Only verified owned bundle members are installed into this isolated test
    # recipient; no source fields are filled into an incomplete codec record.
    root.mkdir()
    for path,raw in files.items():
        target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
