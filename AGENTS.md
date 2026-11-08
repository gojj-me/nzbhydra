# AGENTS.md

Instructions for AI coding agents maintaining NZBHydra v1. Read `README.md` for the project overview, `docs/maintenance.md` for scope and release policy, and `README_DEPLOYMENT.md` before deployment work. Keep detailed deployment instructions in that document and live task status in GitHub issues.

## This repository is public

Treat committed files and published issues, comments, pull requests, commit messages, and release notes as permanently public. Deleting them later does not retract clones, caches, or indexed copies. This file follows the same rules.

- Private sources may inform a fix, but their contents and identifiers must not be published. Describe reproducible NZBHydra behavior using public source references and synthetic examples.
- Do not publish private repository or service names, hostnames, addresses, account names, infrastructure inventories, private tracking references, deployment records, or backup locations and status.
- Do not copy real configuration, databases, search histories, NZB contents, raw incident logs, or assistant conversations into public files or issues. Replacing an API key alone does not sanitize the remaining personal information.
- Use reserved example domains such as `example.com` and `example.invalid`, invented indexer names, and synthetic identifiers and responses in fixtures and documentation. Public provider names and endpoints may be cited when needed to explain an adapter's behavior; never include account-specific URLs or credentials.
- Public project bugs, implementation details, GitHub issue references, and planned releases belong in the public issue/milestone workflow below. Distinguish confirmed behavior, hypotheses, planned work, verified fixes, and published releases. Do not publish private provider internals or operational plans as part of that explanation.
- Review the full diff and all outgoing text as an outside reader before publishing. Automated secret scanning cannot establish that content is safe or non-personal.

## Project map and runtime

- Maintain the original Python 2.7 application; do not substitute NZBHydra2. Modernization is a separate release decision under the policy below.
- `nzbhydra.py` is the application entry point and puts bundled `libs/` on the import path. Do not replace bundled packages with globally installed versions to make a test pass.
- `nzbhydra/web.py` owns web/API behavior; `nzbhydra/search.py` coordinates searches; `nzbhydra/search_module.py` and `nzbhydra/searchmodules/` implement shared indexer behavior and provider adapters; `nzbhydra/database.py` owns models and schema migrations.
- `static/`, `templates/`, and frontend build inputs are part of the application. Preserve shipped assets and establish their build path before changing generated output.
- `maintenance/` implements persistent deployment and recovery; `scripts/` contains Python 3 release tooling; `tests/` contains focused regression tests. Python 3 tooling does not make the legacy application Python 3 compatible.

## Build, run, and validation

Run commands from the repository root. Use an isolated Linux container with the applicable legacy runtime for application tests; use synthetic configuration and a disposable database. Never mount production data into a test container.

- A development application run uses Python 2.7: `python2.7 nzbhydra.py --nobrowser --config <synthetic-settings-file> --database <disposable-database> --logfile <disposable-log>`. Use `--host 127.0.0.1` for local testing. This starts the app and may contact configured indexers; use synthetic settings and isolate networking. Managed deployments use `README_DEPLOYMENT.md` instead.
- `NZBHYDRA_SESSION_DIR` selects a writable session directory when source is immutable. Runtime data, configuration, logs, and sessions must not be written into a verified release tree.
- Full legacy behavioral run: `python3 scripts/run_legacy_regressions.py --image sha256:<full-local-image-id>` tests committed HEAD in an already installed image with no external networking or production mounts. See `README_TESTING.md` for bounds, coverage, environment evidence and cleanup.
- Release metadata: `python3 scripts/check_release_metadata.py`; during release preparation add `--tag <exact-numeric-tag>`.
- Maintenance/tooling checks: `python3 tests/test_maintenance.py`, `python3 tests/test_release_tools.py`, and `python3 tests/test_release_packaging.py`. The first two must also pass under Python 2.7 when changing deployed maintenance code; packaging tests require Python 3.
- Third-party notice verification: `python3 scripts/verify_third_party_notices.py`; `python3 tests/test_release_packaging.py` verifies missing/changed/unlisted notice rejection and staging. Preserve upstream notice bytes; checksums and source associations are evidence, not legal certification.
- Release-content inventory: `python3 scripts/audit_release_content.py --output <temporary-json-file>`; see `docs/audits/legacy-release-content.md` for evidence and limits. Static import/notice indicators do not prove non-use or license completeness.
- Application Linux updater regression: `python2.7 -B tests/test_platform_cleanup.py`, with synthetic manager selection and no real updates or network access.
- Metadata credential regression: `python2.7 -B tests/test_metadata_credentials.py`, with synthetic provider responses, disposable data and no external access. Never reuse the inherited embedded provider credential or record real-account traffic.
- Application TLS regression: `python2.7 -B tests/test_tls.py`, using a loopback HTTPS server and ephemeral synthetic CA/keys to verify trusted-chain success, untrusted-certificate rejection and hostname rejection. Requires the OpenSSL executable in the image; no production data or external providers are used.
- Application Binsearch regression: `python2.7 -B tests/test_binsearch.py`, covering synthetic current HTML, local filters, search-cache paging, individual download links, details and explicit NFO unavailability.
- Application NZBIndex details/NFO regression: `python2.7 -B tests/test_nzbindex_details.py`, including real authenticated XML/JSON API rendering with synthetic responses.
- Application NZBIndex regression: `python2.7 -B tests/test_nzbindex.py`, using synthetic JSON/HTML and request-contract checks.
- Application search-lock regression: `python2.7 -B tests/test_search_lock.py`, covering exception exits, waiting requests and fixed-label diagnostics.
- Application logging regression: `python2.7 -B tests/test_redaction.py`, with invented credentials, managed handlers and disposable SQLite state.
- Application rate-limit regression: `python2.7 -B tests/test_rate_limit.py`, with synthetic HTTP responses and disposable SQLite state.
- Application retention regression: `python2.7 -B tests/test_retention.py`, with synthetic data and no provider access.
- Application authentication regression: `python2.7 -B tests/test_indexer_disable.py`, using the bundled dependencies and disposable SQLite data. Run relevant additional application tests for the behavior being changed.
- Packaging: `python3 scripts/package_release.py --tag <existing-numeric-0.2.x-tag> --output <temporary-output-directory>` builds artifacts from that immutable tag; it does not publish or deploy them. Do not create a release tag merely to test packaging.
- `.github/workflows/release-metadata.yml` checks metadata and Python 3 tooling. Its success alone does not verify Python 2.7 application compatibility. `.github/workflows/release-assets.yml` packages assets for an explicitly published stable legacy release; it does not deploy to a running container.
- Documentation-only edits need link, command, consistency, and privacy review, not a production restart or an invented behavior test. Report exactly which checks ran and any limits or inconclusive results.

## Temporary-resource cleanup

- Before closing an issue, identify the temporary resources created for its work and verify whether each is still required. At closure, or immediately afterward if already closed, remove issue-owned resources explicitly confirmed unnecessary; issue closure alone is not proof that an artifact is disposable.
- Check for leftovers after every test run, including failed, interrupted and timed-out runs, and repeat the check at issue closure. Docker's `--rm` is insufficient: a container left in `Created` state may remain. Verify the final inventory rather than assuming cleanup succeeded.
- Inspect exact container identities, state and mounts before removal. Remove only confirmed disposable test containers and their unneeded anonymous test volumes, plus unneeded issue-owned temporary files, staging directories and test artifacts. Never use broad Docker/container/volume/image pruning as issue cleanup.
- Preserve production services/data, the required legacy image, persistent maintenance state, selected/previous releases, recovery snapshots/backups, committed regression tests/fixtures and anything needed by another open issue or investigation. A closed issue does not authorize deleting recovery material.
- Record completed cleanup and any justified retention in the completion handoff. Keep sensitive inventories and paths private; public issue updates contain only generic outcomes. If ownership or continued need is uncertain, retain the resource and clarify before deletion.

## Behavior, tests, and dependencies

- Keep changes focused and follow the surrounding code style. Runtime and deployed maintenance changes must remain Python 2.7 compatible. Do not perform broad reformatting or dependency upgrades as a side effect of a fix.
- Add meaningful regression coverage for changed behavior using synthetic inputs, isolated data, bounded waits, and deterministic assertions. Use descriptive `test_*.py` names consistent with this repository; do not import another project's test naming rules.
- For adapter/API changes, assert outgoing HTTP methods, paths, query parameters, and bodies as applicable, as well as parsed results and error handling. A canned successful response does not prove that a filter or identifier reached the provider.
- Preserve existing API/configuration semantics unless a change is explicitly scoped. Test relevant omitted, empty, zero, false, malformed, and boundary values; do not assume they are interchangeable. Document provider-specific limits, date boundaries, paging behavior, and partial results only when established.
- Distinguish a valid empty result from failed, timed-out, or malformed responses. Do not report a failed query as proof that nothing matches. Keep authentication, rate-limit, connection, and parsing failures distinguishable without exposing secrets.
- Bound retries, pagination, response sizes, and background work where relevant. A caller timeout does not establish that underlying work was cancelled. Diagnose concurrency and CPU/hang symptoms with evidence before claiming a common cause or resolution.
- Before modifying bundled libraries, inspect the actual vendored version, its callers, license, and runtime constraints. Test the public behavior affected by a change, not just imports or mocks. Preserve required attribution and avoid unsupported upgrade claims.
- Database changes need an idempotent migration for existing databases as well as correct new-database behavior. Validate on disposable data, including interrupted/repeated execution where relevant, and follow the documented snapshot/recovery path before production changes.

## Security and deployment discipline

- Never print or publish credentials, API keys, cookies, authorization headers, or signed download URLs. Check query strings, redirects, exception messages, lazy logging arguments, and request/response bodies; a signed URL can itself grant access.
- Never disable TLS certificate or hostname verification as a repair for a provider failure. Investigate endpoint validity, certificate chains, and runtime trust support separately.
- Keep authentication and access controls intact. Test both permitted and denied paths when changing protected endpoints or indexer scheduling.
- Use the documented persistent maintenance path for managed deployments. Do not edit an active immutable release, use the original source-overwrite updater, or replace the current image/runtime during legacy maintenance.
- Before production activation or data changes, follow the documented backup, verification, health-check, and rollback requirements. Distinguish application version, exact source revision, maintenance-tool revision, channel, and included verified fixes; a target milestone is not the running version.
- Do not introduce automatic activation, a new scheduler, or a channel/policy change merely as part of testing. Preserve pinned test builds and the documented update trust boundary.

## Development
- Start legacy Python 2.7 maintenance releases at 0.2.300 and continue in 0.2.x, fixing the application within the current Docker image. Do not replace the runtime or image in this series.
- Release 0.3.0 must deliver both the modernized application (Rust or the latest stable Python release available when selected) and a new Docker image. Then continue 0.3.x until 0.4.0 is explicitly chosen.
- Maintain NZBHydra v1. Preserve compatibility with the legacy runtime until an explicitly versioned migration is tested.
- Target Linux containers. Assess future runtime and image changes separately from legacy application fixes.
- Use the persistent deployment path implemented in issue #3 for subsequent fixes; its first integrated fix is #9; read README_DEPLOYMENT.md before deployment work.
- Keep release-fixes.json synchronized with included verified issue fixes; release tooling must bind version, changelog, tag, source revision, artifacts, and descriptor.
- Keep fixes focused, preserve source attribution and third-party licenses, and validate behavior before release.
- Do not delete bundled dependencies, frontend build sources, fixtures, or runtime branches merely because they are old. Establish references and verify behavior first.

## Task tracking
- GitHub issues and milestones are the authoritative roadmap, task backlog, and source of task status. Do not maintain a competing task list in documentation or local notes.
- Track all substantive project work, including bugs, enhancements, investigations, deployment work, and documentation, under labeled GitHub issues. Reuse an existing issue when it covers the work; do not create duplicates or one issue per shell command.
- Before creating or restructuring multi-part work, ask the user whether to use a checklist in one issue or linked sub-issues, presenting a concise suggested grouping. Do not choose the granularity, split/merge issues, or convert tracking formats without that decision. Once chosen, maintain progress without repeatedly asking unless the structure needs to change.
- Keep partial completion visible in the agreed format. Mark only verified criteria complete; leave partial or unverified criteria open. Report completed/total counts and outstanding work; any percentage is by item count, not effort. Never describe a partially complete issue as finished.
- Before starting work, find the relevant issue or create a focused issue with acceptance criteria. Keep its scope, progress, blockers, and milestone current; leave unscheduled work without a milestone.
- Link related issues, dependencies, user-approved parent/sub-issues, pull requests, and release references where useful. Record blocking relationships explicitly and avoid duplicate issues.
- When an agreed decision changes, audit all affected repository files, issue scopes, milestone assignments, and descriptions. Verify the published GitHub content after pushing before reporting completion.
- Reference the issue from implementation commits and pull requests. Use closing references only when that change fully resolves the issue.
- Close completed issues after verifying their acceptance criteria, recording the implementation reference and validation. If cancelled, superseded, or duplicated, close with the reason and link to the replacement or canonical issue. Reopen an issue if its completion proves incorrect.
- Closing an implementation issue does not imply it has shipped; record the release separately. Close a release milestone after its release is published and remaining work has been resolved or explicitly rescheduled.
- At each substantive task handoff, refresh the open target milestone and give the maintainer an updated recommended remaining sequence, the single next recommended action and why, plus blockers or decisions. Separate confirmed implementable defects from bounded validation/investigation and work awaiting evidence; never promise a fix for an undiagnosed symptom.
- Reference an open issue ID for every known remaining gap or unvalidated path. If none exists, disclose the tracking omission and obtain the required checklist/sub-issue choice before restructuring. Do not bury remaining work in a closing caveat.
- Keep the current recommended sequence on GitHub's milestone/issue records; documentation describes the process and links to GitHub rather than copying the live backlog. Recommendations do not authorize changing approved issue scope, structure, milestone assignments or release acceptance criteria.
- Apply the privacy rules below to issue bodies, comments, relationships, pull requests, and release notes as well as tracked files.

## Privacy
- Public files must contain reusable project information, not personal computer layouts, customer details, infrastructure inventories, deployment records, backup status, or assistant conversations.
- Never commit passwords, tokens, private keys, recovery codes, cookies, authentication stores, or secret-bearing logs and exports to any Git repository, including private repositories.
- Private repository visibility does not authorize storing arbitrary customer or personal information.
- Store credentials in a credential manager or secret store. Keep non-secret private operational notes outside tracked files; .local/ is ignored but is not a security boundary or a synchronization mechanism.
- Review staged changes and all externally published text for private information. Secret scanners do not detect every privacy issue.

## Keeping these instructions current

Update this file alongside changes to commands, entry points, compatibility constraints, and conventions. Keep `README.md` user-focused and link to the detailed policy and deployment documents. Do not copy a live backlog or private operational notes into this file.
