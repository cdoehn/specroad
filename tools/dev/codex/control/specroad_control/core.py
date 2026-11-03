"""Delegate complete package validation to the locally installed Core."""
from pathlib import Path
import subprocess
from .config import Config, child_environment
from .errors import ControlError
from .contracts import facts
from .local import decode_object


class Core:
    def __init__(self, config: Config):
        self.config = config

    def call(self, operation: str, path: Path, reference: Path | None = None) -> dict:
        if self.config.core_python is None:
            raise ControlError("core_unavailable", "Configure the existing PatchHarbor Python interpreter.")
        argv = [str(self.config.core_python), "-I", "-B", str(Path(__file__).with_name("ph_bridge.py")), operation, str(path)]
        if reference is not None:
            argv.append(str(reference))
        try:
            completed = subprocess.run(argv, cwd=self.config.repository, env=child_environment(self.config),
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       timeout=120, check=False)
            if len(completed.stdout) > 65536:
                raise ValueError
            response = decode_object(completed.stdout)
            if response.get("ok") is not True or completed.returncode != 0:
                raise ControlError(response.get("error", "core_rejected"), "Native Core validation failed; no candidate is accepted.")
            data = facts(response["data"], operation)
            if not isinstance(data, dict):
                raise ValueError
            return {**data, "path": str(path)}
        except ControlError:
            raise
        except (OSError, subprocess.TimeoutExpired):
            raise ControlError("core_unavailable", "The configured Core interpreter did not complete its read-only validation.") from None
        except (KeyError, ValueError, TypeError, UnicodeError, RecursionError):
            raise ControlError("core_protocol_error", "Unexpected Core bridge response.") from None

    def result(self, path: Path) -> dict:
        return self.call("result", path)

    def patch(self, path: Path) -> dict:
        return self.call("patch", path)

    def validate(self, path: Path, source: dict) -> dict:
        data = self.call("validate", path, Path(source["path"]))
        if data.get("reference_sha256") != source["sha256"] or data.get("binding_matches") is not True or data.get("binding") != source["binding"]:
            raise ControlError("binding_mismatch", "The patch or source Result changed.")
        return data
