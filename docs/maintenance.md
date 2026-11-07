# Maintenance and release policy

This document describes public project policy. Machine-specific instructions, personal workflows, deployment details, incident records, and credentials do not belong here.

## Scope and compatibility

Maintain the original NZBHydra v1 application, with Linux containers as the supported distribution target. Native Windows and macOS packaging are outside scope; development tools may run on other systems.

Debian 10, 11, 12, and 13 are requested Docker host compatibility targets, not a claim that the application or Docker vendor currently supports every version. A host runs the Docker engine and kernel; the image supplies the application runtime and userspace. Compatibility must be tested against the specific architecture, kernel, Docker version, storage, permissions, networking, and image. Do not publish a support claim before verifying that combination. Older hosts require a separately documented legacy compatibility policy.

All releases before 0.3.0 fix the existing Python 2.7 application within the current Docker image. Keep that application update path available without replacing the runtime or image. Release 0.3.0 must deliver both the modernized application and a new independently maintained Docker image. No runtime or image change is implemented by this documentation.

## Versioning and changelog

- version.txt is the authoritative application version. The imported baseline is 0.2.233.
- The next legacy application release is 0.2.300, fixing the existing Python 2.7 implementation within the current Docker image. Continue compatible legacy fixes as 0.2.301, 0.2.302, and subsequent 0.2.x releases.
- Release 0.3.0 combines a modernized application and a new Docker image; both are required. Choose Rust or the latest stable Python release available when the runtime is selected through issue #6, including a newer Python major version if one exists. Exclude prereleases; no Python version or language is fixed yet. Issue #7 delivers the new image using the selected runtime. Afterward, continue as 0.3.x until the maintainer explicitly chooses 0.4.0.
- Keep version.txt and the released changelog at the current baseline until release preparation; a milestone is not a published release.
- Preserve changelog.md, its separator, its descending `### <version>` headings, and its existing Added/Changed/Fixed wording. The application's changelog reader depends on this structure.
- At release preparation, add the new version section at the top of the existing version entries and update version.txt in the same change. Do not add an Unreleased heading that changes the first version heading consumed by the legacy reader.
- Documentation-only changes do not advance the application version. Track unfinished work in issues and release milestones, not as completed changelog entries.
- Use a Git tag matching version.txt exactly, consistent with the original numeric tags. Publish release notes matching that changelog section and create archives from that immutable tag.
- Reject a release if its version, first changelog version, tag, or packaged version.txt disagree. scripts/check_release_metadata.py checks these constraints, with an optional --tag value.
- release-fixes.json records verified issue fixes included by release packaging. Keep it synchronized before preparing a tag.
- package.json contains historical frontend build metadata; its version is not the application release authority.
- Define a new series and explicit compatibility/migration policy before publishing breaking runtime or data changes. Do not present historical 0.x numbering as a promise of strict Semantic Versioning.

## Release and deployment requirements

[README_DEPLOYMENT.md](../README_DEPLOYMENT.md) defines the persistent application deployment design, startup/recreation behavior, update channels, activation, recovery, and validation boundaries. Keep that design in one place rather than duplicating it here. [Issue #3](https://github.com/gojj-me/nzbhydra/issues/3) tracks implementation, alongside the first fix in #9; subsequent fixes use the tested deployment path.

A release requires reviewed public-safe artifacts, matching version/changelog/tag/package metadata, behavioral validation in the applicable runtime, and verified update/recovery behavior. The metadata CI job alone does not establish application compatibility. Managed builds disable the original in-application source-overwrite updater. Use the persistent maintenance commands instead; installation is explicit and is not performed merely by reading documentation.

## Database retention

Search-result retention uses the configured day cutoff with a strict older-than comparison. Schema version 22 adds a `SearchResult.firstFound` index for new and existing databases. Migration is repeatable and completes before the schema version advances.

Search requests only offer to schedule best-effort cleanup; they do not count expired rows or wait for cleanup. One background job at a time uses a separate SQLite connection, deletes at most four batches of 250 rows, and checks a one-second execution budget using SQLite's progress handler. SQLite lock waits are limited to 250 ms. These limits do not guarantee interruption of an operating-system storage stall. Cleanup is eligible again after 60 seconds, or after 300 seconds following a failure; further searches trigger remaining work. Expiration is therefore gradual, not immediate deletion of the entire backlog. No independent scheduler is installed.

A failed unfinished batch is rolled back; earlier committed batches remain committed. Cleanup failures do not by themselves abort a search. Search persistence helpers do not retry queued-result timeouts, since those timeouts do not cancel underlying work. A database result timeout reaching the web handler returns a controlled HTTP 503 with a retry interval rather than a successful empty result. Queue depth, worker liveness, and cleanup duration diagnostics help investigation without logging SQL parameters or database contents. These safeguards alone do not establish the cause or resolution of a wider CPU hang.

Before activating schema changes, follow the deployment snapshot and recovery requirements. Returning to older code alone does not restore the earlier database state.

## Provider rate limits

HTTP 429 and recognized Newznab request/download-limit error envelopes establish a persisted per-indexer cooldown. `Retry-After` accepts nonnegative delay-seconds or an HTTP date, following [HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.3). Zero delay gets a minimum one-second cooldown; missing, malformed, or past values use a fixed 15-minute fallback. This fallback does not claim to know a provider's quota or reset schedule. A later existing disable time is never shortened.

Search selection and request admission both enforce an active rate-limit cooldown, including when the general temporary-disable override is enabled. Network requests are serialized per indexer through response classification and status persistence; other indexers retain independent admission. Pending paging stops after a limit response, and a skipped queued search is not recorded as another attempted search. Cooldowns survive application restart using the existing status fields, so no schema migration is required. An overlapping successful result cannot clear an active cooldown; after expiry a successful request can clear it. Permanent authentication disablement still requires explicit re-enablement.

Rate-limit status records only a controlled explanation and the next permitted attempt, not the response body, raw retry header, or credential-bearing URL. Generic connection failures and authentication errors keep their existing behavior. Separate logging-redaction work remains tracked in GitHub; this change does not claim to sanitize all historical error paths. Provider configuration/capability probes and direct downloader requests that bypass the shared indexer search/access path are outside this cooldown mechanism.

## Credential redaction in diagnostics

Application-managed console and file handlers redact complete recognized credential values after message formatting, including exception tracebacks and messages from child loggers. Structured dictionaries/lists, lazy formatting arguments, common credential query/header names, URL user information, signed-URL credential fields, and percent-encoded query keys/values are covered. Redaction failures produce a fixed diagnostic placeholder instead of the original message. The sanitizer operates on diagnostic copies; it must never modify live request URLs, authentication data, or saved application configuration.

New API-access error text and indexer-status reasons are sanitized before model saves. Existing log text is sanitized when viewed through the application or included in a debug-log export. Debug settings mask recognized credential fields, including the signing secret, with fixed placeholders rather than credential-derived hashes. Original historical log/database files and previously generated exports are not rewritten or erased by an update. Recovery backups remain private operational artifacts.

Redaction is not a general privacy guarantee: logs and debug bundles can still contain searches, personal information, private infrastructure details, unknown credential formats, or unlabelled values. Review and minimize any material before sharing it. Never publish a real configuration/database or assume that replacing an API key makes an incident log public-safe.

## Search-result lock recovery and timeout diagnostics

Search-result processing owns the shared database lock through a context manager, which releases it on successful processing and exception exits, including queued-result timeouts. Related application lock owners use context managers as well. The change preserves the controlled database-unavailable response and does not cancel or retry uncertain database work.

Database timeout logs include a fixed operation chain for recognized application call sites, such as search, save-search, persist-result, or provider-status updates. Unrecognized paths are labelled unclassified. Diagnostics never inspect source lines, request contents, SQL/parameters, exception text or frame-local values. Queue depth and worker liveness remain supplemental observations; empty queues and live threads do not prove progress. This exception-safety fix does not establish the original cause of a database timeout or resolve every potential CPU/hang path.

## NZBIndex search compatibility

NZBIndex search uses the public frontend's JSON search endpoint, with page-based pagination and current size/age query parameters. Search metadata is mapped to Hydra identifiers, byte sizes, UTC posting times, groups and individual NZB/collection links. A valid empty JSON envelope is an empty result; provider errors and malformed/unsupported response shapes produce controlled parsing errors.

Legacy HTML parsing remains available for recognized result tables and branded, visible no-results messages. Missing containers/tables/bodies and malformed rows are checked before dereferencing; unexpected page contents are never dumped into diagnostics. Search-title cleanup and configured result restrictions remain applicable. NFO and API details-refresh compatibility is tracked separately in issue #18.

## NZBIndex NFO and details contract

Issue #18 validates the details path against the public collection JSON endpoint, replacing the retired release-page scraper. Refreshed details must preserve provider identifiers and metadata while the Hydra API retains its own result identifier and download URL. Provider errors, missing collections and malformed metadata must not become successful empty results or page dumps.

The verified public collection contract supplies metadata and a file manifest, not NFO contents. The integration returns explicit NFO unavailability, with no call to the retired NFO HTML route and no claim that the collection contains no NFO file. This describes the integration's verified contract, not every possible provider service.

## Binsearch search and collection compatibility

Binsearch uses the public frontend's GET `/search` contract with a query and zero-based `page` parameter. Each provider page contains up to 25 collections. Its cursor is stored per indexer within each cached search, independently of the caller's requested result limit; a title fallback resets that cursor. The adapter checks the returned current-page marker and next-page state, and stops on an empty or final page. Missing layouts, malformed rows and non-advancing pages are failures, not successful empty results. No retired `index.php` requests or unsupported historical size/age query parameters are generated.

Size and age restrictions are applied locally through shared result acceptance. Displayed sizes are rounded binary units and posting dates are estimated from relative age labels, including calendar month/year offsets. These estimates cannot provide byte-exact size or second-exact age boundaries. Category information is unavailable and remains unknown. A final-page total describes the enumerated collections, not an independently verified global count.

Details use the selected collection's `/details/<id>` page. Refreshed size sums its displayed file sizes, and age uses its oldest displayed file age; rounding can differ from search summaries. Individual download links use GET `/nzb?id=<id>`, selecting one collection rather than every search result. An NZB may contain multiple files belonging to that collection. The verified frontend has no NFO retrieval contract; the integration reports explicit unavailability without requesting the retired NFO endpoint or asserting that a collection contains no NFO file. Access restrictions and HTTP/provider failures retain normal error handling; no challenge bypass or TLS relaxation is used.

## Repository cleanup

Removed unsupported Windows distribution build files, retired Travis configuration, and the old Ubuntu Xenial Dockerfile/Compose example. That Dockerfile was not a LinuxServer image recipe and referenced missing certificate/key inputs. A reproducible image recipe must be introduced and tested separately.

Retain runtime code, bundled libraries and notices, tests, fixtures, compiled frontend assets, frontend source/build inputs, and Linux service examples until their dependencies and release relevance have been assessed. Remove or modernize them through focused changes with validation, rather than treating age as proof they are unnecessary. Existing Windows-specific updater branches remain pending that assessment.

## Work tracking

Use [GitHub issues](https://github.com/gojj-me/nzbhydra/issues) for concrete tasks with acceptance criteria and [milestones](https://github.com/gojj-me/nzbhydra/milestones) for intended releases. Together they are the project roadmap and authoritative record of all tasks, scope, status, and progress. All substantive work—bugs, enhancements, investigations, deployment, and documentation—must be covered by a labeled issue. Reuse existing issues instead of duplicating them; individual commands and routine checks belong to the relevant task, not separate issues. Do not duplicate the live backlog in documentation or local notes.

Legacy stabilization and the next release are tracked by the [0.2.300 milestone](https://github.com/gojj-me/nzbhydra/milestone/1). Modernization is tracked separately by the [0.3.0 milestone](https://github.com/gojj-me/nzbhydra/milestone/2). Issues use bug for confirmed defects, enhancement for improvements, documentation for documentation work, and question for undecided proposals. Labels describe the work; the milestone schedules it. Do not invent bug reports before a defect has been identified and reproduced.

### Tracking structure and partial completion

Before creating or restructuring multi-part work, ask the maintainer to choose a checklist in one issue or linked sub-issues, with a concise proposed grouping. Do not select the granularity or split, merge, or convert issues without that decision. Keep the agreed tracking current without repeatedly requesting the same choice. Mark only verified criteria complete, leave partial work open, and report completed/total counts plus remaining work. Percentages describe item counts, not effort; a partially complete issue stays open.

### Issue lifecycle and relationships

1. Before implementation, search for an existing issue. Create a focused issue if needed, describing the desired outcome and acceptance criteria. Use synthetic examples and public-safe evidence.
2. Keep progress, decisions, blockers, and validation on that issue. Assign a release milestone only when the work is selected for that release. Without a board, record active or blocked status in issue updates; an open issue alone does not imply work has started.
3. Link related issues and pull requests with issue references. Use parent/sub-issue relationships only in the agreed tracking structure, and record blocking relationships when appropriate; otherwise explicitly state dependencies with links. Reference the relevant issue in commits and pull requests. Use closing references only for changes that fully resolve it.
4. Close an issue when its acceptance criteria have been verified and its outcome, implementation reference, and validation are recorded. A commit, pull request, or end of an assistant session alone is not proof of completion.
5. Close cancelled, superseded, or duplicate issues with an explanation and a link to the replacement or canonical issue where applicable. Reopen work if the claimed resolution proves incorrect.
6. Distinguish implementation completion from publication: record which release ships the change. Close a release milestone after publishing the release and resolving or explicitly moving any unfinished work.

Issue text, comments, attachments, and relationship descriptions are public project content. Personal operational records and credentials must not be copied there; keep private context separate from the public task status.

### Release handoffs and recommendations

At each substantive handoff, review the target milestone's open issues and provide an updated recommended sequence toward release, the single next action and its reason, and unresolved blockers or maintainer decisions. Distinguish confirmed defects ready for implementation from validation/investigation and issues awaiting evidence. An undiagnosed symptom must not be presented as a promised fix. Reference an issue ID for every known remaining validation gap; obtain the agreed tracking-structure decision if that gap is not already tracked.

Keep the current sequence in GitHub milestone/issue records, with live status on each issue. Do not duplicate that backlog in repository documentation. Review unresolved milestone items before release and explicitly resolve or reschedule them with the maintainer; a recommendation alone does not change accepted scope or release criteria.

### Scheduling

Future work remains in issues without a milestone until selected for a release. Separate roadmap/planned labels or a Project board are not required. Add a board only if the backlog needs more detailed workflow tracking.

The [runtime modernization decision](https://github.com/gojj-me/nzbhydra/issues/6) and [new Docker image](https://github.com/gojj-me/nzbhydra/issues/7) both belong to 0.3.0. The image build depends on the runtime decision, and both deliverables must be validated before that release. Neither a Python port nor a Rust rewrite has been selected. Preserve observable behavior and assess dependency work, implementation effort, maintenance burden, and measured performance before choosing.

## Source history

See source-provenance.md for the imported version and commit. Preserve the original Git history and licensing. Public provenance must not contain local paths or deployment observations.
