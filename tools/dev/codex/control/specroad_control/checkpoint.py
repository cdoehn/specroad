"""Native manual snapshot capture, used only by an explicit start-current request."""
from pathlib import Path
import subprocess

from .config import child_environment
from .errors import ControlError
from .local import decode_object


def capture(config):
    if config.core_python is None:
        raise ControlError('core_unavailable', 'Configure the existing PatchHarbor interpreter.')
    argv = [str(config.core_python), '-I', '-B', str(Path(__file__).with_name('ph_checkpoint.py')),
            str(config.apply_directory), config.repo_id, str(config.exchange)]
    try:
        result = subprocess.run(argv, cwd=config.repository, env=child_environment(config),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=120, check=False)
        if len(result.stdout) > 65536:
            raise ValueError
        reply = decode_object(result.stdout)
        if result.returncode != 0 or reply.get('ok') is not True:
            raise ControlError(reply.get('error', 'checkpoint_failed'), 'Native checkpoint was not captured.')
        path = Path(reply['path'])
        if (not path.is_absolute() or path.parent.resolve() != config.exchange.resolve()
                or path.is_symlink() or not path.is_file()):
            raise ValueError
        return path
    except ControlError:
        raise
    except (OSError, subprocess.TimeoutExpired):
        raise ControlError('checkpoint_unavailable', 'The native checkpoint process did not complete.') from None
    except (ValueError, KeyError, TypeError):
        raise ControlError('checkpoint_invalid', 'Invalid native checkpoint reply.') from None
