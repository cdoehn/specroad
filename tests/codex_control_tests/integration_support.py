"""Private test installation; deliberately no production Result attestation."""
from hashlib import sha256
from pathlib import Path
from specroad_control.local import REPO, json_write, write_private, private_dir


def install_fixture_release(paths):
    root = paths.home / 'releases' / ('a' * 40)
    private_dir(root)
    files = {'control': (REPO/'control').read_bytes()}
    files.update({p.relative_to(REPO).as_posix(): p.read_bytes()
                  for p in (REPO/'specroad_control').glob('*.py')})
    for name, data in files.items():
        private_dir((root/name).parent)
        write_private(root/name, data)
    receipt = {'format_version': 1, 'commit': 'a'*40, 'result_sha256': 'b'*64,
               'files': {n: sha256(b).hexdigest() for n,b in files.items()}}
    json_write(root/'release.json', receipt)
    json_write(paths.home/'active-release.json', receipt)
    return root
