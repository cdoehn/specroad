"""Baseline comparison through the shared source and semantic-diff contracts."""


def compare_baselines(before_root, before_reference, after_root, after_reference, *,
                      timing_bounds=None, before_configuration_id=None,
                      after_configuration_id=None):
    """Compare verified owned snapshots; opaque resource changes fail explicitly.

    References are canonical Baseline IDs or explicit record bytes. No Git,
    checkout, materialization, current-tree fallback or release authorization.
    The returned result has exactly the existing semantic-diff contract.
    """
    from ..query.comparison_sources import ComparisonSourceSnapshot, compare_sources

    before = ComparisonSourceSnapshot(before_root, kind='baseline', reference=before_reference)
    after = ComparisonSourceSnapshot(after_root, kind='baseline', reference=after_reference,
                                     expected_project_id=before.configuration.project_id)
    return compare_sources(before, after, timing_bounds=timing_bounds,
        before_configuration_id=before_configuration_id,
        after_configuration_id=after_configuration_id)
