"""Public export refusals at retained-runtime and final publication boundaries."""
from pathlib import Path
from textwrap import indent

import pytest

from support.transport_outbound import run_request, tree
from test_transport_outbound import distribution
from test_transport_outbound_edges import _export_setup


def intervene(method, mutation):
    """Inject a real environmental change at one observable operation boundary."""
    return ("from pathlib import Path\nimport os,sys,types\n"
            "from specroad.transport.outbound import OutboundExport\n"
            f"original = OutboundExport.{method}\n"
            "def changed(self, *args, **kwargs):\n" + indent(mutation, '    ') +
            "\n    return original(self, *args, **kwargs)\n"
            f"OutboundExport.{method} = changed\n")


def references(root):
    return sorted((root/'output').glob('*_Result_*.zip'))


@pytest.mark.parametrize('method', ('capture', 'assemble', 'publish'))
@pytest.mark.parametrize('change', ('copy_bytes', 'copy_identity', 'copy_mode',
                                    'copy_directory_mode', 'foreign_module', 'source_identity'))
def test_runtime_is_still_bound_at_each_export_phase(tmp_path, distribution, method, change):
    root, value = _export_setup(tmp_path, distribution)
    before = tree(root)
    mutations = {
        'copy_bytes': "path=self.runtime._prepared.path\npath.write_bytes(path.read_bytes()+b'changed')",
        'copy_identity': "path=self.runtime._prepared.path\nraw=path.read_bytes()\npath.rename(path.with_suffix('.saved'))\npath.write_bytes(raw)\npath.chmod(0o600)",
        'copy_mode': "self.runtime._prepared.path.chmod(0o644)",
        'copy_directory_mode': "self.runtime._prepared.path.parent.chmod(0o755)",
        'foreign_module': "sys.modules['patchharbor.foreign']=types.ModuleType('patchharbor.foreign')",
        'source_identity': "path=self.runtime_input.path\nraw=path.read_bytes()\npath.rename(path.with_suffix('.saved'))\npath.write_bytes(raw)",
    }
    result = run_request(tmp_path, value, before=intervene(method, mutations[change]))
    assert result['code'] == (6 if change == 'source_identity' else 7), result
    assert not (tmp_path/'output/handoff.zip').exists()
    assert len(references(tmp_path)) == (0 if method == 'capture' else 1)
    assert tree(root) == before


@pytest.mark.parametrize('method', ('capture', 'assemble', 'publish'))
@pytest.mark.parametrize('change', ('permissions', 'replacement', 'symlink'))
def test_private_workspace_cannot_be_replaced_or_exposed(tmp_path, distribution, method, change):
    root, value = _export_setup(tmp_path, distribution)
    before = tree(root)
    mutation = {
        'permissions': "self.workspace.chmod(0o755)",
        'replacement': "saved=self.workspace.with_name(self.workspace.name+'-saved')\nself.workspace.rename(saved)\nself.workspace.mkdir(mode=0o700)\n(self.workspace/'foreign').write_bytes(b'keep')",
        'symlink': "saved=self.workspace.with_name(self.workspace.name+'-saved')\nself.workspace.rename(saved)\nself.workspace.symlink_to(saved, target_is_directory=True)",
    }[change]
    result = run_request(tmp_path, value, before=intervene(method, mutation))
    assert result['code'] == 7, result
    assert not (tmp_path/'output/handoff.zip').exists()
    assert len(references(tmp_path)) == (0 if method == 'capture' else 1)
    assert tree(root) == before
    if change == 'replacement':
        assert [p.read_bytes() for p in (tmp_path/'output').glob('.specroad-outbound-*/foreign')] == [b'keep']


@pytest.mark.parametrize('method', ('assemble', 'publish'))
@pytest.mark.parametrize('change,code', (('exchange', 6), ('output_permissions', 7),
                                       ('new_repository', 7), ('plan_boundary', 6)))
def test_operating_boundary_is_rechecked_after_reference_capture(tmp_path, distribution, method, change, code):
    root, value = _export_setup(tmp_path, distribution)
    original = tree(root)
    mutation = {
        'exchange': "other=self.output.root.parent/'other-exchange'\nother.mkdir()\nself.api.configure_exchange_directory(other, repository=self.project.root)",
        'output_permissions': "self.output.root.chmod(0o777)",
        'new_repository': "import subprocess\nother=self.output.root/'new-repository'\nother.mkdir()\nsubprocess.run(['git','init','-q',str(other)],check=True)\nsubprocess.run(['git','-C',str(other),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-qm','Fixture'],check=True)\nself.api.register(other)",
        'plan_boundary': "from dataclasses import replace\nself.plan=replace(self.plan,output_directory=self.output.root.parent)",
    }[change]
    result = run_request(tmp_path, value, before=intervene(method, mutation))
    assert result['code'] == code, result
    assert not (tmp_path/'output/handoff.zip').exists()
    assert len(references(tmp_path)) == 1
    # Changing Exchange intentionally updates only the repository-local PH
    # configuration. No normative bytes, index, refs or history are changed.
    after = tree(root)
    if change == 'exchange':
        assert {n for n in set(original)|set(after) if original.get(n) != after.get(n)} == {'.patchharbor/config.json'}
    else:
        assert after == original


@pytest.mark.parametrize('collision', ('existing', 'casefold', 'parent_casefold', 'symlink'))
def test_late_output_collisions_preserve_foreign_files(tmp_path, distribution, collision):
    root, value = _export_setup(tmp_path, distribution)
    before = tree(root)
    foreign = tmp_path/'output'/('HANDOFF.ZIP' if collision == 'casefold' else 'handoff.zip')
    if collision == 'parent_casefold':
        value['options']['--output'] = 'nested/handoff.zip'
        foreign = tmp_path/'output/NESTED/foreign'
    mutation = f"foreign=Path({str(foreign)!r})\nforeign.parent.mkdir(parents=True,exist_ok=True)\n"
    if collision == 'symlink':
        target = tmp_path/'foreign.zip'
        target.write_bytes(b'keep')
        mutation += f"foreign.symlink_to(Path({str(target)!r}))"
    else:
        mutation += "foreign.write_bytes(b'keep')"
    result = run_request(tmp_path, value, before=intervene('publish', mutation))
    assert result['code'] in (6, 7), result
    assert foreign.read_bytes() == b'keep'
    assert tree(root) == before
    assert len(references(tmp_path)) == 1
    if collision in ('casefold', 'parent_casefold'):
        assert not (tmp_path/'output'/value['options']['--output']).exists()


@pytest.mark.parametrize('method', ('assemble', 'publish'))
def test_changed_source_after_capture_never_gets_a_new_reference(tmp_path, distribution, method):
    root, value = _export_setup(tmp_path, distribution)
    mutation = "(self.project.root/'late-input.bin').write_bytes(b'new source')"
    result = run_request(tmp_path, value, before=intervene(method, mutation))
    assert result['code'] == 6, result
    assert (root/'late-input.bin').read_bytes() == b'new source'
    assert len(references(tmp_path)) == 1
    assert not (tmp_path/'output/handoff.zip').exists()


def test_projection_collision_is_preserved_without_adding_project_bytes(tmp_path, distribution):
    root, value = _export_setup(tmp_path, distribution)
    before = tree(root)
    mutation = "p=self.workspace/'project'\np.mkdir()\n(p/'foreign').write_bytes(b'keep')"
    result = run_request(tmp_path, value, before=intervene('assemble', mutation))
    assert result['code'] == 6, result
    assert tree(root) == before
    projections = list((tmp_path/'output').glob('.specroad-outbound-*/project'))
    assert len(projections) == 1
    assert {p.name:p.read_bytes() for p in projections[0].iterdir()} == {'foreign':b'keep'}
    assert len(references(tmp_path)) == 1
    assert not (tmp_path/'output/handoff.zip').exists()


def test_incomplete_projection_write_is_an_io_failure_with_reference_retained(tmp_path, distribution):
    root, value = _export_setup(tmp_path, distribution)
    before = tree(root)
    mutation = """write=os.write
def short(fd,data):
    path=os.readlink('/proc/self/fd/'+str(fd))
    if '/project/' in path and '.specroad-outbound-' in path:
        return 0
    return write(fd,data)
os.write=short"""
    result = run_request(tmp_path, value, before=intervene('assemble', mutation))
    assert result['code'] == 5, result
    assert result['outcome']['summary']['transport_failure']['reason'] == 'staging_short_write'
    assert len(references(tmp_path)) == 1
    assert not (tmp_path/'output/handoff.zip').exists()
    assert tree(root) == before
