"""Validate persisted lifecycle facts without treating stale data as live status."""
import math
import uuid
from .errors import ControlError
from .local import Paths, json_read


def read_state(paths: Paths) -> dict | None:
    previous = json_read(paths.state_file)
    if previous is None:
        return None
    try:
        if type(previous["schema"]) is not int or previous["schema"] != 1:
            raise ValueError
        if previous["desired"] not in ("running", "paused"):
            raise ValueError
        if previous["phase"] not in ("idle", "paused", "working", "pausing", "stopping", "stopped"):
            raise ValueError
        if type(previous["active_job"]) is not bool:
            raise ValueError
        if type(previous["pid"]) is not int or previous["pid"] < 1:
            raise ValueError
        if not isinstance(previous["run_id"], str) or str(uuid.UUID(previous["run_id"])) != previous["run_id"]:
            raise ValueError
        for name in ("started_at", "updated_at"):
            if type(previous[name]) not in (int, float) or not math.isfinite(previous[name]) or previous[name] < 0:
                raise ValueError
        if previous["phase"] in ("working", "pausing", "stopping") and not previous["active_job"]:
            raise ValueError
        if previous["phase"] in ("idle", "paused", "stopped") and previous["active_job"]:
            raise ValueError
        delay = previous.get('start_delay')
        if 'start_delay' in previous:
            if (type(delay) is not dict or set(delay) != {'seconds', 'remaining_seconds', 'waiting'}
                    or type(delay['seconds']) not in (int, float) or not 0 <= delay['seconds'] <= 86400
                    or type(delay['remaining_seconds']) not in (int, float)
                    or not 0 <= delay['remaining_seconds'] <= delay['seconds']
                    or type(delay['waiting']) is not bool
                    or delay['waiting'] != (delay['remaining_seconds'] > 0)
                    or delay['waiting'] and (previous['active_job'] or previous['phase'] == 'stopped')):
                raise ValueError
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ControlError("invalid_state", "Persisted state is invalid; it has been preserved for review.") from None
    return previous
