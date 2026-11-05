"""Read-only validation in a synthetic project; never read local environment files."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import yaml


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'BACity-'
BASE = 'docker-compose.yml'
SOCIAL = 'compose.social.yml'
RUNTIME = 'infrastructure/social/runtime.override.example.yml'
PUBLIC = 'infrastructure/social/public-api-runtime.override.yml'
PRODUCTION = 'compose.production.yml'
COMBINATIONS = [(BASE,), (BASE, SOCIAL), (BASE, SOCIAL, RUNTIME),
                (BASE, SOCIAL, RUNTIME, PUBLIC), (PRODUCTION,)]


def main():
    values = {
        'POSTGRES_USER': 'ci_user', 'POSTGRES_PASSWORD': 'ci_password', 'POSTGRES_DB': 'bacity_ci',
        'APP_DOMAIN': 'app.bacity.test', 'API_DOMAIN': 'api.bacity.test',
        'SOCIAL_ADMIN_HOST': 'admin.bacity.test', 'SOCIAL_BIND_ADDRESS': '127.0.0.1',
        'SOCIAL_CONSUMER_DB_ROLE': 'bacity_public_runtime',
        'SOCIAL_WORKER_KEY': 'ci-synthetic-worker-key-' + 'x' * 32,
        'APIFY_API_TOKEN': '', 'SCRAPINGANT_API_KEY': '',
        'SOCIAL_L4_ENABLED': 'false', 'SOCIAL_L4_COLLECTION_ENABLED': 'false',
        'SOCIAL_L4_PUBLICATION_ENABLED': 'false', 'APIFY_ENABLED': 'false', 'SCRAPINGANT_ENABLED': 'false',
    }
    for role in ['ADMIN', 'GATEWAY', 'RELAY', 'MAINTENANCE', 'PUBLIC_API']:
        values[f'SOCIAL_{role}_DATABASE_URL'] = 'postgresql+psycopg2://ci_user:ci_password@postgres:5432/bacity_ci'
    # Config is evaluated from copies with no .env, social.env or production env.
    # Docker config never starts services or contacts an application database.
    with tempfile.TemporaryDirectory(prefix='bacity-ci-compose-') as directory:
        project = Path(directory)
        for name in {name for combination in COMBINATIONS for name in combination}:
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(APP / name, target)
        env_file = project / 'ci.env'
        env_file.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
        environment = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR', 'SYSTEMROOT') if key in os.environ}
        environment['COMPOSE_DISABLE_ENV_FILE'] = '1'
        environment['COMPOSE_PROJECT_NAME'] = 'bacity-ci-validation'
        for combination in COMBINATIONS:
            command = ['docker', 'compose', '--env-file', str(env_file), '--project-directory', str(project), '--profile', '*']
            for name in combination:
                command += ['-f', str(project / name)]
            subprocess.run(command + ['config', '--no-env-resolution', '--quiet'], env=environment, check=True)
            print('Valid Compose:', ' + '.join(combination), flush=True)
    profile = json.loads((APP / 'infrastructure/social/seccomp_profile.json').read_text())
    if profile['defaultAction'] != 'SCMP_ACT_ERRNO' or not profile['syscalls']:
        raise SystemExit('Invalid collector seccomp profile')
    tracked = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z', '--', 'BACity-/*.sh'])
    for name in tracked.decode().split('\0'):
        if name:
            subprocess.run(['sh', '-n', str(ROOT / name)], check=True)
    subprocess.run(['sh', '-n', str(APP / 'control')], check=True)
    subprocess.run(['node', '--check', str(APP / 'services/api/app/social/static/app.js')], check=True)
    workflow = yaml.load((ROOT / '.github/workflows/ci.yml').read_text(), Loader=yaml.BaseLoader)
    assert workflow['on'] == {'push': '', 'workflow_dispatch': ''}, 'CI must run unfiltered pushes and manual dispatch only'
    assert set(workflow['jobs']) == {'backend', 'crawler', 'mobile', 'infrastructure'}
    assert workflow['permissions'] == {'contents': 'read'}
    assert all('needs' not in job and 'if' not in job for job in workflow['jobs'].values()), 'All four jobs must run independently'
    print('Workflow structure, seccomp JSON, shell scripts and social panel JavaScript syntax are valid.')


if __name__ == '__main__':
    main()
