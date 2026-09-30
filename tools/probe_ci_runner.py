"""Print a bounded machine-readable runner decision; never starts a workflow."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))
from ci_support.runners import probe_runner

if __name__ == '__main__':
    print(json.dumps(probe_runner(), sort_keys=True))
