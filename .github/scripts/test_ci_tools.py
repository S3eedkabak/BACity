"""A green report must mean tests ran, without hidden skips or failures."""
import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest


spec = importlib.util.spec_from_file_location('ci_report_tests', Path(__file__).with_name('report_tests.py'))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

infra_spec = importlib.util.spec_from_file_location('ci_validate_infrastructure', Path(__file__).with_name('validate_infrastructure.py'))
infrastructure = importlib.util.module_from_spec(infra_spec)
infra_spec.loader.exec_module(infrastructure)


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


@pytest.mark.parametrize('combination', infrastructure.COMBINATIONS)
def test_compose_resolves_service_env_files_without_reading_owner_configuration(tmp_path, monkeypatch, combination):
    source = tmp_path / 'source'
    source.mkdir()
    for name in {name for group in infrastructure.COMBINATIONS for name in group}:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(infrastructure.APP / name, target)
    owner_files = ['.env', '.env.production', 'social.env']
    marker = 'OWNER_ONLY_CONFIGURATION_MUST_NOT_BE_COPIED'
    for name in owner_files:
        (source / name).write_text(marker)
    monkeypatch.setattr(infrastructure, 'APP', source)
    project = tmp_path / 'validation'
    project.mkdir()
    env_file = infrastructure.prepare_compose_project(project)
    for name in ['ci.env', '.env', '.env.production']:
        content = (project / name).read_text()
        assert 'POSTGRES_USER=ci_user' in content and marker not in content
    assert not (project / 'social.env').exists()
    command = ['docker', 'compose', '--env-file', str(env_file), '--project-directory', str(project), '--profile', '*']
    for name in combination:
        command += ['-f', str(project / name)]
    result = subprocess.run(command + ['config', '--quiet'], env=infrastructure.compose_environment(), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert all((source / name).read_text() == marker for name in owner_files)
