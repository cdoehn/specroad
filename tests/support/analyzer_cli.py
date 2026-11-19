"""Real files for published Analyzer examples, without pretending workers exist."""
import json

from specroad.cli.results import thaw


def example_inputs(root, command):
    request = command.protocol.example.as_dict()
    if command.command_id in ('analyzer.list', 'analyzer.describe'):
        return request
    from test_analyzer_evaluation import prepared
    _, _, snapshot, package = prepared(root)
    (root / 'request.json').write_bytes(snapshot.canonical_bytes)
    (root / 'report.json').write_bytes(package.original_bytes)
    return request


def assert_example_outcome(command, result):
    """Keep all prior success assertions; bind new unavailable examples exactly."""
    unavailable = command.command_id in ('analyzer.run', 'analyzer.evaluate')
    assert result.exit_code == (5 if unavailable else 0), (command.command_id, result.as_dict())
    if command.command_id == 'analyzer.run':
        from specroad.analyzers.packages import ReportPackage
        package = ReportPackage(json.dumps(thaw(result.result)).encode())
        assert package.reports and all(r.data['run_status'] == 'unavailable' for r in package.reports)
        assert all(r.data['coverage']['open'] == r.data['coverage']['expected'] for r in package.reports)
    elif command.command_id == 'analyzer.evaluate':
        rows = result.result['evaluation']['reports']
        assert rows and all(r['currentness'] == 'unavailable' and r['request_binding_verified'] for r in rows)
        assert result.result['execution_complete'] and not result.result['gate_passed']
