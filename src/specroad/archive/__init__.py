"""Content-addressed snapshot bytes, independent of Baseline and Git metadata."""
from .objects import (ObjectReference, SnapshotObject, SnapshotObjectStore,
                      check_object_retention, read_snapshot_object)
from .baseline import BaselineManifest, build_baseline_manifest
from .verification import (verify_baseline_snapshot, verify_baseline_objects,
                           baseline_integrity_gate)
from .materialization import show_baseline_snapshot, materialize_baseline_snapshot
from .comparison import compare_baselines
from .readiness import ReleaseBaselineReadiness, assess_release_baseline_readiness

__all__ = ['ObjectReference', 'SnapshotObject', 'SnapshotObjectStore',
           'check_object_retention', 'read_snapshot_object',
           'BaselineManifest', 'build_baseline_manifest', 'verify_baseline_snapshot',
           'verify_baseline_objects', 'baseline_integrity_gate',
           'show_baseline_snapshot', 'materialize_baseline_snapshot', 'compare_baselines',
           'ReleaseBaselineReadiness', 'assess_release_baseline_readiness']
