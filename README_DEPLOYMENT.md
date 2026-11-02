# Persistent application deployment

Target design for Python 2.7 application updates within the existing Docker image, starting with 0.2.300. Implementation, validation, and current task status are tracked in [issue #3](https://github.com/gojj-me/nzbhydra/issues/3). This document is a design specification, not an executable installation procedure or a claim that deployment tools already exist.

## Purpose

Build the persistent deployment path alongside the authentication-disable fix in [issue #9](https://github.com/gojj-me/nzbhydra/issues/9), then use the same tested path for every subsequent fix. The fix can be developed and tested independently; activating it in a running installation depends on the deployment path being ready.

Update a complete, verified application revision and perform a controlled restart. Do not overwrite individual source files while Python is running: loaded modules and new files could otherwise represent different revisions. This is application deployment, not a replacement container image or runtime migration. The modernized application and new image belong to 0.3.0.

## Proposed persistent layout

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

These are proposed application interface paths, not a description of a personal deployment. The implementation may refine them with corresponding documentation changes. Existing user configuration, databases, and logs stay separate from application release directories and must never be included in release archives.

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

The intended user interface is one deployment operation selecting a published release or an explicitly chosen test revision. No command is documented as available until implemented and tested.

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

Issue #3 owns the deployment acceptance criteria; [issue #1](https://github.com/gojj-me/nzbhydra/issues/1) covers regression infrastructure, [issue #2](https://github.com/gojj-me/nzbhydra/issues/2) release packaging, and [issue #5](https://github.com/gojj-me/nzbhydra/issues/5) public release documentation. Record progress and validation on those issues rather than maintaining a second checklist here.

Validate with isolated synthetic data before use: restart, recreation with the same mount, missing-release restoration, offline startup, rejected downloads, concurrent updates, failed health checks, and recovery. Do not exercise production indexers or download clients as part of test setup.

## Privacy

Publish only generic behavior and synthetic examples. Keep machine identities, credentials, real configuration, raw logs, search histories, operational measurements, and backup records out of public documentation and issues. No private key or API token belongs in release artifacts or Git history, including private repositories.
