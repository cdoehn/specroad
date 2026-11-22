"""21.a: real read-only config command; defaults and precedence are observable."""
import json
import pytest
from specroad.cli.application import execute_request, dispatch_result
from specroad.cli.result_schemas import validate_result_document
from specroad.model.language_policy import default_language_policy
from support.model import configuration_file, put
from support.read_only import inventory, no_write_attempts


@pytest.mark.parametrize('version',['0.2.0','0.3.0'])
@pytest.mark.parametrize('representation',['argv','mapping'])
def test_config_show_materializes_defaults_and_override_origins_without_model(tmp_path,version,representation):
    configuration_file(tmp_path,schema_version=version,validation_policy={'fail_on':'error'},
        language_policy={'mixed_languages':{'section':'error'}}, resource_limits={'model_bytes':321})
    put(tmp_path,'spec/goals/invalid.json',b'broken model -- must not be loaded')
    before=inventory(tmp_path)
    with no_write_attempts():
        result=(dispatch_result(['config','show','--project',str(tmp_path),'--strict','--format=json'])
            if representation=='argv' else execute_request({'command_id':'config.show',
                'options':{'--project':str(tmp_path),'--strict':True}}).result)
    assert result.exit_code==0,result.as_dict()
    value=result.as_dict()['result'];validate_result_document('config-show-v1',value)
    assert inventory(tmp_path)==before
    effective=value['effective_configuration']
    expected=default_language_policy();expected['mixed_languages']['section']='error'
    assert effective['language_policy']==expected
    assert effective['validation_policy']['fail_on']=='warning'
    assert [r['source'] for r in value['origins']['/validation_policy/fail_on']]==['default','project','cli:strict']
    assert effective['transaction_policy']=={'retain_receipts':True}
    assert effective['srx_policy']=={'numeric_policy_version':'srx-decimal-v1','decimal_precision':34}
    assert effective['resource_limits']['query_default_limit']==100
    assert value['origins']['/language_policy/mixed_languages/section'][-1]=={'source':'project','value':'error'}
    assert not value['model_loaded'] and not value['full_validation_passed'] and not value['profile_composition_verified']

    assert effective['validation_policy']['required_relation_review']=='current'
    assert value['origins']['/resource_limits/model_bytes']==[{'source':'project','value':321}]
    assert effective['resource_limits']['query_result_count']==10000
