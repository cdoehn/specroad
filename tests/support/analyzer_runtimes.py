"""Immutable original offline package installations for adapter integration tests."""
import pytest

from language_packaging.build import build_language, wheel_files
from language_packaging.inventory import LANGID, NUMPY
from language_packaging.runtime_matrix import load_runtime_matrix
from language_packaging.verify import verify_package
from support.portable import ROOT


@pytest.fixture(scope='module')
def runtime_factory(tmp_path_factory):
    """Reuse only immutable installations; each case owns its request/project."""
    matrix = load_runtime_matrix()
    installations = {}

    def obtain(minor='3.14'):
        if minor not in installations:
            root = tmp_path_factory.mktemp('acceptance-' + minor)
            archive = root / 'addon.zip'
            build_language(ROOT / 'src', matrix['wheelhouse'], minor, archive)
            manifest, files, _ = verify_package(archive)
            site = root / 'site'
            site.mkdir()
            payload = {n[len('adapter/'):]: raw for n, raw in files.items()
                       if n.startswith('adapter/')}
            for name, wheel in {'numpy': NUMPY[minor], 'py3langid': LANGID}.items():
                payload.update(wheel_files(files['wheels/' + wheel['filename']], name, wheel))
            for name, raw in payload.items():
                target = site / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            installations[minor] = site, matrix['interpreters'][minor], manifest
        return installations[minor]

    return obtain
