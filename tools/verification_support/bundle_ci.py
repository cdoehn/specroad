"""Bundle trailers are descriptive metadata, never an automatic CI trigger."""
import re

SHA = re.compile(r"[0-9a-f]{40}\Z")


def commit_sha(value):
    if type(value) is not str or SHA.fullmatch(value) is None:
        raise ValueError("A full lowercase GitHub commit SHA is required")
    return value


def bundle_metadata(message):
    if type(message) is not str:
        raise ValueError("Commit message must be text")
    keys = ("SpecRoad-Bundle", "SpecRoad-Bundle-Final")
    records = {key: [] for key in keys}
    for line in message.splitlines():
        key, sep, value = line.partition(":")
        if sep and key in records:
            records[key].append(value.strip())
    if not any(records.values()):
        return None
    if any(len(records[key]) != 1 for key in keys):
        raise ValueError("Missing or ambiguous bundle trailers")
    number, final = records[keys[0]][0], records[keys[1]][0]
    if re.fullmatch(r"[0-9]{3,9}", number) is None or int(number) < 1 or f"{int(number):03d}" != number:
        raise ValueError("Invalid bundle number")
    if final not in ("true", "false"):
        raise ValueError("Invalid completion trailer")
    return int(number), final == "true"


def select_ci(event, ref, sha, message, *, mode="parallel"):
    """Only an explicit manual request runs full regression, in parallel.

    The old UI value 'auto' is accepted for already registered dispatch forms;
    it is an alias for 'parallel', never a bundle-number-dependent decision.
    Bundle trailers remain descriptive metadata, not a scheduling trigger.
    """
    sha = commit_sha(sha)
    if event not in ("push", "workflow_dispatch") or mode not in ("auto", "both", "parallel"):
        raise ValueError("Unsupported CI event or mode")
    metadata = bundle_metadata(message)
    number, final = metadata if metadata else (None, False)
    return {"commit_sha": sha, "run_full": event == "workflow_dispatch",
            "mode": "parallel", "bundle_number": number,
            "bundle_final": final, "trigger": event}
