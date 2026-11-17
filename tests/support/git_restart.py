"""User-like local Git checkouts and real writes, only inside owned test roots.

No production API restores Git or repairs a source root. All stored receipts
come from successful native writes; interrupted roots are retained verbatim.
"""
import os
import subprocess

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.changes import prepare_publication_check, project_lock, publish_guarded_change
from specroad.qualification.project import validate_project
from specroad.validation import ModelGate
from support.folds import edit
from support.publication import ALLOW
from support.targets import POLICY, plan


def project_files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and '.git' not in p.relative_to(root).parts}


def git(root, *arguments):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT='0')
    result = subprocess.run(['git', '-c', 'user.name=Synthetic test author',
        '-c', 'user.email=fixture@example.invalid', '-c', 'core.hooksPath='+os.devnull,
        '-c', 'commit.gpgsign=false', *arguments], cwd=root, env=env,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def save(root):
    saved = project_files(root)
    git(root, 'init', '--initial-branch=fixture')
    git(root, 'add', '--force', '--', *sorted(saved))
    git(root, 'commit', '-m', 'Synthetic complete native project')
    return git(root, 'rev-parse', 'HEAD'), saved


def checkout(source, destination, commit):
    git(destination.parent, 'clone', '--no-hardlinks', '--no-checkout', '--',
        str(source), str(destination))
    git(destination, 'checkout', '--detach', commit)
    return destination


def _project_gates(model):
    """Qualify the actual candidate documents, not the unchanged source model.

    These small projects deliberately include a primary document and a stored
    configuration. Their mandatory services run the full native validator;
    no test callback substitutes a guessed successful qualification.
    """
    artifact_paths = {document.path for document in model.documents}
    resources = {path: raw for path, raw in model.source_files.items()
                 if path not in artifact_paths}

    def dependencies(context):
        return context.dependency_result({identity: list(context.all_ids)
                                          for identity in context.subjects})

    def check(context):
        validate_project({**resources, **{d.path: d.content for d in context.documents}})
        return context.result()

    return tuple(ModelGate(name, 'git-restart-native-target-v1', dependencies, check,
                           model._sources_sha256)
                 for name in ('document_model', 'configuration'))


def new_write(root, request, transaction, statement):
    model = InspectionSnapshot(root, None).model
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    candidate = plan(model, [edit(goal, statement)], request_id=request)
    gates = _project_gates(model)
    check = prepare_publication_check(candidate, model, policy=POLICY, gates=gates)
    with project_lock(root, kind='writer', command='change apply', project_id='sample',
                      request_id=request, transaction_id=transaction) as held:
        return publish_guarded_change(check, held_lock=held, authority=ALLOW, gates=gates).data
