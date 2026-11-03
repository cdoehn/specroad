"""One command, one reply; no interactive or model-based polling."""
import argparse
import json
from . import service, commands
from .daemon import run
from .ipc import request
from .state import read_state
from .errors import ControlError
from .local import Paths


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SpecRoad Control: manually operated, event-driven Dev automation.")
    parser.add_argument("--config", help="Absolute path to the external config.toml")
    parser.add_argument("command", choices=("install", "start", "stop", "pause", "resume", "status", "run", "configure", "check", "probe", "recover", "handover", "reconcile-apply", "reconcile-blocked", "disk-space", "migrate", "deploy"))
    parser.add_argument('--min-free-gb', type=float, help='Minimum free decimal GB; only with disk-space')
    parser.add_argument("--thread-id", help="Explicit existing Dev thread UUID")
    parser.add_argument("--thread-cwd", help="Explicit existing metadata cwd of the new Dev thread")
    parser.add_argument("--from-thread-cwd", help="Explicit present cwd of the original thread")
    parser.add_argument("--defer", action="store_true", help="Queue handover for the existing worker")
    parser.add_argument("--resume-after", action="store_true", help="Resume development after deferred handover")
    parser.add_argument("--result", help="Initial Result for configure, completed Result for reconciliation/deploy")
    parser.add_argument("--legacy-config", help="Explicit legacy config for offline migration")
    parser.add_argument("--codex", help="Absolute existing Codex executable")
    parser.add_argument("--core-python", help="Absolute Python in the existing PatchHarbor installation")
    parser.add_argument("--transport", choices=("exec", "app-server-proxy"))
    args = parser.parse_args(argv)
    if args.min_free_gb is not None and args.command != 'disk-space':
        parser.error('--min-free-gb is only allowed with disk-space')
    if args.command == "configure" and not args.thread_id:
        parser.error("configure requires --thread-id; --result is only needed to initialize runtime state")
    if args.command == "handover" and (not args.thread_id or not args.thread_cwd):
        parser.error("handover requires --thread-id and --thread-cwd")
    if args.command != "handover" and args.thread_cwd:
        parser.error("--thread-cwd is only allowed with handover")
    if args.command not in ("configure", "handover") and args.thread_id:
        parser.error("--thread-id is only allowed with configure or handover")
    if args.command in ("reconcile-apply", "reconcile-blocked") and not args.result:
        parser.error(args.command + " requires --result")
    if args.command not in ("configure", "reconcile-apply", "reconcile-blocked", "deploy") and args.result:
        parser.error("--result is only allowed with configure, reconciliation or deploy")
    if args.command != "configure" and any((args.codex, args.core_python, args.transport)):
        parser.error("setup options are only allowed with configure")
    if args.command != "handover" and (args.from_thread_cwd or args.defer or args.resume_after):
        parser.error("handover options are only allowed with handover")
    if args.resume_after and not args.defer:
        parser.error("--resume-after requires --defer")
    if args.legacy_config and args.command != 'migrate':
        parser.error('--legacy-config is only allowed with migrate')
    if args.command == 'deploy' and not args.result:
        parser.error('deploy requires --result from successful SpecRoad Apply')
    try:
        paths = Paths.discover(args.config)
        if args.command not in ('migrate', 'stop') and not paths.config.exists() and Paths.legacy().config.exists():
            raise ControlError('migration_required', 'Explicit offline migration is required; legacy state is preserved.')
        if args.command == 'migrate':
            from .migration import migrate
            result = migrate(paths, legacy_config=args.legacy_config)
        elif args.command == 'deploy':
            from .releases import deploy
            result = deploy(paths, args.result)
        elif args.command == 'run':
            from .releases import active_entrypoint
            from .local import REPO
            if active_entrypoint(paths).parent != REPO:
                raise ControlError('uninstalled_runtime', 'Run the installed, verified Control release.')
            return run(paths)
        elif args.command == 'disk-space':
            from .disk_space import set_limit, status as disk_status
            result = set_limit(paths, args.min_free_gb) if args.min_free_gb is not None else disk_status(paths)
        elif args.command == "handover":
            from .handover import handover
            if args.defer:
                from .handover_queue import enqueue
                result = enqueue(paths, thread_id=args.thread_id, thread_cwd=args.thread_cwd,
                                 from_cwd=args.from_thread_cwd, resume_after=args.resume_after)
            else:
                result = handover(paths, thread_id=args.thread_id, thread_cwd=args.thread_cwd,
                                  from_cwd=args.from_thread_cwd)
        elif args.command in ("reconcile-apply", "reconcile-blocked"):
            from .apply_reconcile import enqueue
            result = enqueue(paths, args.result, blocked=args.command == "reconcile-blocked")
        elif args.command == "configure":
            result = commands.configure(paths, thread_id=args.thread_id, result=args.result,
                                        codex=args.codex, core_python=args.core_python, transport=args.transport)
        elif args.command in ("check", "probe", "recover"):
            result = getattr(commands, args.command)(paths)
        elif args.command in ("install", "start", "stop"):
            result = getattr(service, args.command)(paths)
        elif args.command in ("pause", "resume"):
            result = request(paths, args.command)
        else:
            from .handover_queue import public_status
            try:
                result = {"worker_reachable": True, **request(paths, "status")}
            except ControlError as exc:
                if exc.code != "not_running":
                    raise
                result = {"worker_reachable": False, "state": None, "last_state": read_state(paths)}
            try:
                result["systemd"] = service.inspect()
            except ControlError as exc:
                result["systemd"] = {"error": exc.code}
            pending = public_status(paths)
            if pending is not None:
                result['handover'] = pending
            from .apply_reconcile import public_status as apply_status
            try:
                pending_apply = apply_status(paths)
                if pending_apply is not None:
                    result['apply_reconciliation'] = pending_apply
            except ControlError as exc:
                result['apply_reconciliation'] = {'error': exc.code}
            if not result.get('worker_reachable'):
                from .disk_space import status as disk_status
                try:
                    result['disk_space'] = disk_status(paths)
                except ControlError as exc:
                    result['disk_space'] = {'error': exc.code}
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
        return 0
    except ControlError as exc:
        print(json.dumps({"ok": False, "error": exc.code, "message": str(exc)}))
        return 1
    except OSError:
        print(json.dumps({"ok": False, "error": "local_io_error", "message": "A local operation failed; no successful action is claimed."}))
        return 1
