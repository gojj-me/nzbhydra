# Legacy regression validation

[Issue #1](https://github.com/gojj-me/nzbhydra/issues/1) owns regression readiness. GitHub issues and milestones hold live acceptance/status; this document describes the repeatable procedure, not a release approval or a second roadmap.

## Requirements and command

Use Python 3.7 or later, Git and Docker on a Linux test machine with the applicable legacy image already installed. Supply its full local image ID after checking it against the intended runtime. Do not pull an arbitrary replacement image, mount production data, or install global packages to satisfy imports.

```sh
python3 scripts/run_legacy_regressions.py --image sha256:<full-local-image-id>
```

Replace the placeholder with the actual ID; it is intentionally not a project-wide personal deployment setting. The runner tests **committed HEAD**, including on a candidate branch. Commit intended changes first; uncommitted changes and ignored/private files are excluded. No tag is created and no release, production service or update policy is changed. The runner prints the source commit/image ID for a private verification receipt and the actual Python, OpenSSL, SQLite, Requests and Peewee versions. Review output before sharing; do not publish machine-specific deployment records.

The demonstrated legacy environment is Python 2.7.18, OpenSSL 1.1.1g, SQLite 3.30.1, bundled Requests 2.12.1 and Peewee 2.8.5. The image supplies the interpreter/native libraries; application imports use the committed bundled libraries. These are observed test versions, not an instruction to upgrade or a claim about every architecture or Docker host.

The runner streams a Git archive into one uniquely labelled disposable container. It uses no host directory mounts, no published ports, no external network, a read-only image filesystem, temporary source/state filesystems and bounded CPU/memory/process resources. Loopback remains available for the synthetic HTTPS and real application startup tests. Each suite has a 90-second limit; the entire run defaults to 600 seconds (`--timeout` can override it). A suite failure stops the run and returns nonzero. Normal completion, failures and outer timeouts remove the exact generated container and its anonymous volumes and verify its absence; temporary host archives are removed. If the host process is forcibly killed or Docker becomes unavailable, inspect the uniquely named/labelled resource before removing it. Never prune unrelated containers, images or recovery material.

## Coverage

| Area | Selected evidence |
| --- | --- |
| Indexer request admission | Permanent authentication disablement and persisted rate limits, retries and concurrency |
| Search/API behavior | Binsearch and NZBIndex request/parse/paging/details contracts; authenticated XML/JSON rendering; metadata failure behavior and database timeout handling |
| Database compatibility | Retention index for new/existing databases, repeated migration, bounded cleanup, timeout/lock exception safety |
| Settings and restart | Real entry-point startup twice with the same synthetic configuration/database; API key enforcement; persisted settings, schema version and a sentinel database record |
| Version handling | Application comparator across legacy/next-series boundaries; inherited version/changelog consistency |
| TLS and diagnostics | Trusted/untrusted/wrong-host loopback HTTPS; credential redaction and diagnostic exports |
| Linux-only scope | Updater selection, configured/global Git lookup and immutable-managed-source guard |

The selected fix suites are listed explicitly in `scripts/legacy_regression_suite.py`; each runs in a separate Python process. `tests/test_release_readiness.py` adds comparator and real startup/restart checks. The inherited `test_Update` and `test_Categories` suites are also explicitly run with unittest. The inherited update comparator test tests a local helper; the new comparator test calls the actual application function.

The historical broad pytest entry point is not used as a release gate: it relies on unavailable pytest/test infrastructure, old setup decorators/configuration/recordings, retired provider contracts and performance workloads. The configuration-suite import was checked in the applicable image and fails with `ImportError: No module named pytest`; no package was installed to mask that limitation. Its safe update/category cases are selected explicitly. This does not claim all inherited tests pass. Focused synthetic replacements cover the changed release behavior without replaying historical provider recordings or using real credentials. Any newly confirmed defect or relevant uncovered acceptance requirement must be tracked in GitHub before release; do not hide it as a skipped passing test.

## Separate Python 3 tooling checks

Run from the checkout:

```sh
python3 scripts/check_release_metadata.py
python3 scripts/verify_third_party_notices.py
python3 tests/test_maintenance.py
python3 tests/test_release_tools.py
python3 tests/test_release_packaging.py
```

The metadata CI workflow runs these checks. Its green status does not establish Python 2.7 application compatibility; the explicit legacy runner supplies separate behavioral evidence. When deployed maintenance code changes, its compatible maintenance/release-tool tests must additionally run under Python 2.7 as required by AGENTS.md.

## Limits and release handoff

This validation does not contact real indexers, rebuild frontend assets, prove all host combinations, exercise the service-manager container recreation path, or diagnose an intermittent production CPU hang. Maintenance restart/recreation/recovery acceptance is owned by [#3](https://github.com/gojj-me/nzbhydra/issues/3); compatibility documentation by [#5](https://github.com/gojj-me/nzbhydra/issues/5), partial-result guidance by [#14](https://github.com/gojj-me/nzbhydra/issues/14), CPU/hang evidence by [#8](https://github.com/gojj-me/nzbhydra/issues/8), and final tagged-artifact/release acceptance by [#2](https://github.com/gojj-me/nzbhydra/issues/2). Rerun relevant checks on the final selected release source and archive rather than treating an earlier candidate pass as final publication acceptance.
