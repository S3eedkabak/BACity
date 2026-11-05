# Continuous integration

`/.github/workflows/ci.yml` lives at the Git repository root, above `BACity-/`.
Every push to every branch (including `main`) runs the entire workflow. There
are no pull-request, path-filter or scheduled triggers. The four independent
Ubuntu 24.04 jobs run in parallel; any failure fails CI. New development-branch
pushes cancel superseded runs. Every `main` run has its own concurrency group,
so neither running nor queued `main` builds are cancelled by newer pushes.

| Job | Checks | Infrastructure |
|---|---|---|
| Backend | Entire API suite: authentication, authorization, migrations, PostGIS/map inventory, identity/ingestion, billing, publishers, L4 social, real WebAuthn, browser workflows, Apify/ScrapingAnt fixtures, budgets, durable outbox and database-stop/restart recovery | Disposable PostGIS 16 service at port 55436; Playwright Chromium and the hosted runner's sandbox-enabled Chrome |
| Crawler | Entire crawler suite, including Levels 1–3/L4 integrations, parsers, normalization, deduplication and the complete HTTP → queue → API → map round trip | Local fixture HTTP servers, temporary SQLite/state files; no live crawl |
| Mobile | Locked npm install, TypeScript, all existing Node tests, Expo public config and iOS/Android/web JavaScript exports | Node 24; no external API or native emulator needed |
| Infrastructure | Five Compose combinations, social/security/runtime overlays, workflow structure, seccomp JSON, shell/JS syntax, Alembic graph, existing launcher tests and the existing collector-isolation verification | Docker; only the collector image is built, for its essential network-disabled sandbox proof |

Python 3.12 dependencies reuse the API/social/crawler manifests. The small CI
requirements file adds Playwright 1.64.1, matching the existing collector image,
and PyYAML for workflow validation. pip/npm downloads are cached; dependencies
are still installed on every job. Actions are pinned to verified commit SHAs.
Default token permission is `contents: read`; checkout does not persist credentials.

Redis and OpenSearch configuration is validated, but neither service is started:
no current automated test requires a Redis/OpenSearch connection. PostgreSQL
integration tests use real PostGIS, not a database mock. All existing opt-in tests
are enabled, including the fault-injection test's dedicated container name and
port. Browser availability is checked before pytest; sandbox protections stay on.
Provider acquisition tests use existing mocks/fixtures and need no paid credentials.
No local `.env`, `social.env`, production database, production secret or deployment
is used. Compose validation uses copies and a temporary synthetic environment.
The temporary project also generates synthetic `.env` and `.env.production`
service files: runner Compose 2.38 checks their existence even when environment
resolution is disabled. No owner environment file is copied or made optional.

## Commands

From `BACity-/services/api`:

```sh
python -m pytest tests -q -ra --junitxml="$RUNNER_TEMP/ci-results/backend.xml"
```

From `BACity-/services/crawler`:

```sh
python -m pytest tests -q -ra --junitxml="$RUNNER_TEMP/ci-results/crawler.xml"
```

From `BACity-/apps/mobile`:

```sh
npm ci
npm run typecheck
npm test -- --test-reporter=spec --test-reporter-destination=stdout --test-reporter=junit --test-reporter-destination="$RUNNER_TEMP/ci-results/mobile.xml"
npx --no-install expo config --type public --json
npx --no-install expo export --platform all --output-dir "$RUNNER_TEMP/expo-export"
```

There is no configured mobile lint or Jest command; the existing test runner is
Node's built-in runner. CI does not invent a replacement framework. Bundle
exports do not verify native iOS/Android interaction, rendering or performance.

Infrastructure runs `python .github/scripts/validate_infrastructure.py` from the
Git root, `python -m alembic heads` from the API directory, and:

```sh
# From BACity-/services/api:
python -m pytest tests/social/test_control_launcher.py "$GITHUB_WORKSPACE/.github/scripts/test_ci_tools.py" -q -ra --junitxml="$RUNNER_TEMP/ci-results/infrastructure.xml"
# From BACity-/:
sh infrastructure/social/verify-container.sh
```

The previous branch-filtered CI and manual live-crawl workflow are consolidated
into this workflow. Existing test files/assertions are unchanged. The crawler's
synthetic HTTP end-to-end tests replace reliance on live websites for CI; live
website availability and real paid acquisitions are deliberately not exercised.

## Results, failures and reruns

Open the repository's **Actions → BACity CI**, choose the pushed commit and open
each job. Test logs and the run summary show actual passed/failed/skipped counts.
JUnit reports and synthetic browser screenshots are retained for three days.
**A missing/empty report, any failed test or any skipped test fails CI.** A failed
setup/build step also fails the job, even if its tests passed. There are no allowed
skips at present; fix missing services/dependencies instead of disabling tests.

To diagnose a failure, start at the first failed step, download its artifacts,
reproduce that focused command and fix its cause. A deliberately superseded
development run is cancelled, not passed. Use **Re-run failed jobs** after an
infrastructure outage, or push the correction to trigger all four jobs again.

For manual runs use **Actions → BACity CI → Run workflow**, selecting the branch.
GitHub requires the workflow to exist on the default branch for manual dispatch;
the first approved push of `CI/impl` still runs automatically without a merge.
GitHub uses the workflow committed on the pushed branch. After reviewing that
first run, merge the CI changes into `main` with approval so new branches inherit
them; existing branches need the CI commit incorporated before they use this
workflow instead of their older configuration.
No repository secrets or owner-side service setup are required. Normal repository
Actions permissions/billing must allow GitHub-hosted runners.

New tests under the API/crawler `tests/` directories or Node's existing test
discovery run automatically. For new services or opt-in tests, provision them,
enable their gate and preserve zero skips. Add an explicit CI step if a new lint
or other established automated check is introduced.

## Initial local verification

Implementation was prepared on `CI/impl` from `ui/spectrum-native-20261102` at
`97d0fe8`. Focused validation checks the workflow, dependency installation, all
Compose combinations and CI support code. Complete suites and Linux-only browser,
container sandbox and database fault injection are intentionally deferred to the
first approved GitHub push; local setup validation is not a claimed Actions pass.

Local results: Actionlint 1.7.12 and all five Compose combinations passed; fresh
Python dependency installation and `pip check`, clean `npm ci`, TypeScript and
Expo public config passed. Focused Python checks: **24 passed, 0 failed, 0 skipped**.
Node 24 plus the exact npm/JUnit reporter protocol: **4 passed, 0 failed, 0 skipped**.
Collection-only checks found **668 backend** and **217 crawler** tests. No full
regression suite or Linux-only integration test was rerun locally. No existing
application source, test assertion or dependency manifest was changed.
