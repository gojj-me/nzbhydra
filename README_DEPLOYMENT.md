# Persistent application deployment

Persistent maintenance for Python 2.7 application updates within the existing Docker image, starting with 0.2.300. Implementation, validation, and current task status are tracked in [issue #3](https://github.com/gojj-me/nzbhydra/issues/3). The maintenance tools are implemented under maintenance/. Implementation and validation evidence are recorded in issue #3; preparation of the complete application release is tracked by its release milestone.

## Purpose

Build the persistent deployment path alongside the authentication-disable fix in [issue #9](https://github.com/gojj-me/nzbhydra/issues/9), then use the same tested path for every subsequent fix. The fix can be developed and tested independently; activating it in a running installation depends on the deployment path being ready.

Update a complete, verified application revision and perform a controlled restart. Do not overwrite individual source files while Python is running: loaded modules and new files could otherwise represent different revisions. This is application deployment, not a replacement container image or runtime migration. The modernized application and new image belong to 0.3.0.

## Persistent layout

```text
/config/
├── custom-cont-init.d/
│   └── 50-nzbhydra-maintenance.sh
└── nzbhydra-maintenance/
    ├── bootstrap.sh
    ├── updater/
    ├── releases/
    │   └── <immutable-build-id>/
    ├── current -> releases/<selected-build-id>
    ├── previous -> releases/<last-working-build-id>
    └── state/
```

These are application interface paths, not a description of a personal deployment. Keep documentation synchronized when they change. Existing user configuration, databases, and logs stay separate from application release directories and must never be included in release archives.

The legacy image's custom initialization facility runs the persistent startup hook. On each container start it must idempotently configure application startup to use the selected release. Startup changes made only inside the disposable container filesystem must be reapplied after recreation. Do not assume that every unrelated LinuxServer image has an identical startup interface; validate against the supported legacy image.

## What survives

| Event | Changes only in the container filesystem | Files in the same persistent /config storage |
| --- | --- | --- |
| Stop/start or ordinary restart | Normally retained | Retained |
| Remove and recreate the container | Lost | Retained if the same storage is mounted |
| Replace the container from an image | Lost | Retained if the same storage is mounted; image compatibility must be checked |
| Mount empty or different /config storage | Does not recover previous persistent state | Previous files are unavailable through that new mount |
| Delete or lose the backing persistent storage | Cannot recover the application data from the original image | Lost unless restored from a separate backup |

Persistence is not a backup. Keep verified recovery copies separately and store their locations and actual status privately.

## Startup and update behavior

1. Read the configured channel and selected immutable release/build identifier from persistent state. Distinguish application version from exact source revision.
2. Use an existing verified local release first. Startup must not depend on GitHub being reachable when a working local release is available.
3. Reapply the startup integration after recreation. Validate persistent storage, ownership, executable paths, and the selected runtime before starting the application.
4. If the selected release is missing, attempt to retrieve that exact trusted artifact, validate it, and restore it. Do not silently substitute arbitrary branch contents or an unselected newer build.
5. Recheck published stable releases according to the configured policy. Check-only behavior can report or stage an update; unattended activation must be an explicitly enabled policy. Use bounded timeouts and retries.
6. Retain the last verified working release on network, validation, or update failure. If none is available, stop with a controlled actionable error rather than starting partially downloaded code.
7. Keep release selection and updater/bootstrap state persistent too. Define how updater changes are verified and recovered; bootstrap must not blindly replace itself from a moving branch.

## Deployment operation

The apply command performs one deployment operation for an explicitly selected immutable build. A trusted maintainer must prepare its pinned descriptor first. Stable release assets are built from an immutable numeric tag by scripts/package_release.py and the release-assets workflow. Check reports eligible releases without activation; release --version selects one explicitly.

- Verify a recoverable baseline before changing code or data. Stop writers or use a validated consistent database backup procedure; protect SQLite journal files where relevant.
- Acquire an update lock. Stage a complete artifact in a new directory and validate download success, provenance, checksums, archive safety, file manifest, runtime compatibility, and packaged metadata.
- Never extract untrusted archives over settings, databases, logs, the current release, or the persistent updater. Checksums alone do not establish independent authenticity.
- Quiesce the application, atomically select the new release on the same filesystem, and perform a controlled restart. Define the exact lifecycle behavior for the legacy service manager before implementation.
- Check health and the behavior relevant to the deployed fix. Record the active build only after successful validation; retain the previous selection for recovery.
- On failure, restore the prior application selection. Database rollback requires its matching consistent backup if a migration changed data; switching a symlink alone does not reverse migrations.

## Release and test channels

Normal updates use published stable releases from this repository. Development commits do not silently deploy. Explicit test deployments pin an immutable source commit and verified artifact and record both the application version and build identifier. A selected test build must not be silently replaced by a stable update or a newer branch commit.

At release preparation, version.txt, the first changelog version, Git tag, release notes, and packaged version must agree. The next legacy release is 0.2.300. A test build is not a published release and must not be represented as one.

## Validation boundary

Before creating or restructuring multi-part work, ask the maintainer to choose a checklist in one issue or linked sub-issues, with a concise proposed grouping. Do not select the granularity or split, merge, or convert issues without that decision. Keep the agreed tracking current without repeatedly requesting the same choice. Mark only verified criteria complete, leave partial work open, and report completed/total counts plus remaining work. Percentages describe item counts, not effort; a partially complete issue stays open.

Issue #3 owns the deployment acceptance criteria; [issue #1](https://github.com/gojj-me/nzbhydra/issues/1) covers regression infrastructure, [issue #2](https://github.com/gojj-me/nzbhydra/issues/2) release packaging, and [issue #5](https://github.com/gojj-me/nzbhydra/issues/5) public release documentation. Record progress and validation on those issues rather than maintaining a second checklist here.

Validate with isolated synthetic data before use: restart, recreation with the same mount, missing-release restoration, offline startup, rejected downloads, concurrent updates, failed health checks, and recovery. Do not exercise production indexers or download clients as part of test setup.

## TMDB metadata credential

The application no longer ships a TMDB credential. To enable uncached TMDB/IMDb conversion and movie autocomplete, supply your own [TMDB v3 API key](https://developer.themoviedb.org/docs/authentication-application). This interface uses the v3 `api_key` credential, not a bearer-token value.

The default file is `/config/nzbhydra-maintenance/secrets/tmdb-api-key`. Store only the key and an optional trailing newline in that regular file, outside the checkout. Restrict its directory to the service owner (typically mode 0700) and the file to that owner (typically mode 0600), while allowing the application process to read it. Populate it through your secret manager or a local editor with appropriate access controls; never put the value in Git, a shell command argument, an issue, a chat or a debug bundle.

Precedence is:
1. `NZBHYDRA_TMDB_API_KEY`, if present in the application environment.
2. The regular file named by `NZBHYDRA_TMDB_API_KEY_FILE`, if that variable is present.
3. The default persistent file above.

An explicitly empty environment value/path does not fall back to another credential. Empty, unreadable, non-regular, oversized or invalid key material is unavailable and sends no TMDB request. Values are limited to 4096 printable ASCII characters after surrounding whitespace is stripped; key files are limited to 4098 bytes including a possible CRLF ending. Environment overrides must be restored by the container's own configuration after recreation; the default file survives when the same persistent `/config` storage is mounted.

Credentials are read for each provider request without a global library key. Replacing the file permits the next uncached lookup to use the new value without an application restart. Successful metadata autocomplete results may still be served from the ordinary cache; failed lookups are not cached as empty successes. Cached ID conversions and searches using a query or supplied IMDb ID remain available without a TMDB key. TMDB-dependent autocomplete/conversion requests report controlled HTTP 503 when unavailable, and optional conversion/fallback helpers return no conversion instead of aborting unrelated searches.

No credential is written into saved application settings, configuration exports or debug archives. Secret-file recovery is a separate operator responsibility: do not assume an application settings/data snapshot contains it. Restoring code/data does not rotate or roll back this separately managed credential. Keep any credential recovery material outside Git and diagnostic exports.

Removing inherited values from the current tree does not retract previously published history or revoke another party's credential. Do not reuse the removed value, probe its validity, rerecord real-provider responses or assume that source cleanup performs revocation. The metadata client uses bounded requests with TLS verification preserved and redirects disabled; provider errors do not expose their bodies, URLs or credentials in the returned diagnostic.

## Temporary-resource cleanup

Before issue closure, inventory the temporary containers, volumes, files, staging directories and test artifacts created for that issue. At closure, or immediately afterward for an already closed issue, remove resources explicitly verified unnecessary. Check after every test run as well, including failures, timeouts and interrupted runs. Docker `--rm` does not guarantee cleanup when a container remains in `Created` state; inspect the final inventory explicitly.

Use exact resource identities and inspect container state and mounts before removal. Remove only disposable test containers and their unneeded anonymous test volumes; do not use broad Docker, volume or image pruning. Verify that the intended resources were removed and that the production application remains healthy.

Preserve the existing application image, production data/configuration, persistent maintenance state, selected and previous releases, required archive caches, recovery snapshots/backups and committed regression tests/fixtures. Retain resources needed by another open issue, investigation or recovery procedure. Closing an issue alone does not establish that these are unnecessary or authorize recovery-data deletion; clarify uncertain ownership or retention before removing anything.

The issue completion handoff must state what cleanup was verified and explain any continued retention. Keep operational inventories, resource identities and paths private; public updates describe generic outcomes. This is a manual completion requirement, not a new automatic deletion or retention policy.

## Privacy

Publish only generic behavior and synthetic examples. Keep machine identities, credentials, real configuration, raw logs, search histories, operational measurements, and backup records out of public documentation and issues. No private key or API token belongs in release artifacts or Git history, including private repositories.

## Maintenance commands

Run inside the supported legacy container as root:

```sh
python /config/nzbhydra-maintenance/updater/maintenance.py status
python /config/nzbhydra-maintenance/updater/maintenance.py check
python /config/nzbhydra-maintenance/updater/maintenance.py recover
python /config/nzbhydra-maintenance/updater/maintenance.py --verify-tools
python /config/nzbhydra-maintenance/updater/maintenance.py tools-recover
python /config/nzbhydra-maintenance/updater/maintenance.py apply --descriptor /config/nzbhydra-maintenance/state/candidate.json
```

A candidate descriptor pins source_commit, archive_sha256, application_version, target_release, channel, and included_fixes. It is supplied by the maintainer after testing. Apply downloads the pinned GitHub source archive, validates and stages it, snapshots application data with the service stopped, activates, checks the build header, and restores code/data automatically on failed health checks. Boot restores a missing selected release from the verified archive cache or the pinned GitHub archive; stable-release checking is explicit and check-only. Updater/bootstrap updates require a separately reviewed installation; they do not self-update from a branch.

Status reports exact revision and included fixes. Startup logs and the X-NZBHydra-Build HTTP header identify the running revision. The authenticated version endpoint also includes build metadata. Unreleased test builds retain the current released version.txt; target_release is not a claim of publication. Interrupted application deployments fail closed. The explicit recover command uses the durable transaction record and its matching application/data snapshot; it preserves displaced data for investigation and refuses missing or inconsistent recovery records. It restores the original image startup hook when recovering the original baseline. Do not run recover as a routine update: it intentionally restores older data, so later application changes may be displaced. Without a transaction record or valid snapshot, use the separately verified external recovery backup. Baseline image/data backups remain necessary; automatic failure rollback is not a substitute for disaster recovery.

## Stable releases and activation policy

The default policy is check-only. Run check to discover eligible stable 0.2.x releases. Run release --version <numeric-version> to explicitly install a published stable release. The installer verifies the release is published and not a draft/prerelease, checks both required assets belong to this repository/tag, resolves annotated or lightweight tags to the descriptor commit, verifies the archive checksum, and checks packaged version/changelog consistency. New-runtime releases, downgrades, and retagged same-version replacements are rejected.

Policy is evaluated when maintenance is invoked; setting policy does not install a scheduler. To permit unattended activation, explicitly run policy --mode auto-stable, then invoke update --automatic through an operator-configured schedule. Check-only is restored with policy --mode check. Even with auto-stable enabled, update --automatic does not replace a pinned test build. An explicit release --version selection is required to leave the test channel.

The release-assets workflow runs only after a stable legacy GitHub release is explicitly published. It packages the tagged source with license notices and a source file manifest, emits maintenance.json and SHA256SUMS, and uploads the assets. It does not publish a release or deploy code itself. release-fixes.json records the included verified issue fixes. Missing/incomplete assets fail safely; publication is not proof that artifact creation has completed successfully.

## Trust model

Trust starts with the reviewed local installer and the fixed startup interface, the configured repository owner/control, GitHub's authenticated release/tag responses, and HTTPS certificate verification. Asset checksums bind the downloaded bytes to the release descriptor; they are not independent signatures. The mechanism does not claim protection against a compromised trusted repository administrator or GitHub account. No signing private keys or authentication credentials are stored in Git or release artifacts.

The installed release manifest is verified strictly: missing, altered, or unexpected files and symlinked entries are rejected. The checksum-pinned archive and tag/revision binding preserve the selected build through restoration. Boot will not automatically fall back to a different application version against newer data; use application recover with its matching snapshot instead. Test descriptors are explicit maintainer-supplied pins; branch contents never activate on their own.

## Versioned maintenance-tool upgrades and recovery

The fixed interface-1 startup hook and bootstrap invoke a stable launcher at updater/maintenance.py. It verifies a complete versioned tool bundle under tools/current before executing it, including updater code, bootstrap, hook, and launcher hashes. A verified tools/previous bundle is retained. If a candidate bundle is damaged or a tool-upgrade journal remains, the launcher uses the previous verified bundle. A damaged trusted startup interface fails closed and requires restoration from the local recovery baseline.

Use tools-install --descriptor <pinned-descriptor> to stage and validate a source archive, check Python and shell compatibility, and atomically promote the complete tool version under the maintenance lock. Initial conversion preserves the old flat updater as a content-identified baseline. Later upgrades must preserve the trusted launcher/bootstrap/hook bytes; changing that interface requires a separately reviewed migration and is deliberately rejected by interface 1. The application build is not changed by tools-install.

Use --verify-tools to inspect the active tool revision and its verified manifest. Status reports maintenance_revision separately from source_commit of the application. Use tools-recover to select the verified previous tool bundle and clear an interrupted tool journal. The fixed launcher handles tools-recover even when the selected updater is damaged. These tool operations do not restore or replace application data; application recover is a separate operation.

First installation and startup-interface recovery require a reviewed local installation of the fixed launcher and trusted bootstrap/hook files. Keep their verified baseline outside disposable container storage. Never replace the trusted launcher from a moving branch or disable verification to force an incompatible upgrade.
