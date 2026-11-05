"""A green report must mean tests ran, without hidden skips or failures."""
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location('ci_report_tests', Path(__file__).with_name('report_tests.py'))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


@pytest.mark.parametrize(('cases', 'expected', 'status'), [
    ('<testcase name="one"/><testcase name="two"/>', (2, 0, 0, 2), 0),
    ('<testcase><failure/></testcase>', (0, 1, 0, 1), 1),
    ('<testcase><error/></testcase>', (0, 1, 0, 1), 1),
    ('<testcase><skipped/></testcase>', (0, 0, 1, 1), 1),
    ('', (0, 0, 0, 0), 1),
])
def test_real_counts_and_fail_closed_reporting(tmp_path, monkeypatch, cases, expected, status):
    path = tmp_path / 'results.xml'
    path.write_text(f'<testsuites><testsuite>{cases}</testsuite></testsuites>')
    summary = tmp_path / 'summary.md'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary))
    assert report.counts(path) == expected
    assert report.main([str(path), '--label', 'Fixture']) == status
    assert f'{expected[0]} passed, {expected[1]} failed, {expected[2]} skipped' in summary.read_text()


@pytest.mark.parametrize('content', [None, '<broken'])
def test_missing_or_invalid_report_cannot_pass(tmp_path, monkeypatch, content):
    path = tmp_path / 'results.xml'
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    if content is not None:
        path.write_text(content)
    assert report.main([str(path), '--label', 'Fixture']) == 1
