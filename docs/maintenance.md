# Maintenance and release policy

This document describes public project policy. Machine-specific instructions, personal workflows, deployment details, incident records, and credentials do not belong here.

## Scope and compatibility

Maintain the original NZBHydra v1 application, with Linux containers as the supported distribution target. Native Windows and macOS packaging are outside scope; development tools may run on other systems.

Debian 10, 11, 12, and 13 are requested Docker host compatibility targets, not a claim that the application or Docker vendor currently supports every version. A host runs the Docker engine and kernel; the image supplies the application runtime and userspace. Compatibility must be tested against the specific architecture, kernel, Docker version, storage, permissions, networking, and image. Do not publish a support claim before verifying that combination. Older hosts require a separately documented legacy compatibility policy.

Keep the legacy-image application update path available. An independently built image is a later distribution option, not a prerequisite for fixing the existing application. No replacement image or runtime migration is implemented by this documentation.

## Versioning and changelog

- version.txt is the authoritative application version. The imported baseline is 0.2.233.
- Continue the existing three-component numeric sequence. The next compatible application release is intended to be 0.2.234; it is not released or reserved by a tag yet.
- Preserve changelog.md, its separator, its descending `### <version>` headings, and its existing Added/Changed/Fixed wording. The application's changelog reader depends on this structure.
- At release preparation, add the new version section at the top of the existing version entries and update version.txt in the same change. Do not add an Unreleased heading that changes the first version heading consumed by the legacy reader.
- Documentation-only changes do not advance the application version. Track unfinished work in issues or the roadmap, not as completed changelog entries.
- Use a Git tag matching version.txt exactly, consistent with the original numeric tags. Publish release notes matching that changelog section and create archives from that immutable tag.
- Reject a release if its version, first changelog version, tag, or packaged version.txt disagree. scripts/check_release_metadata.py checks these constraints, with an optional --tag value.
- package.json contains historical frontend build metadata; its version is not the application release authority.
- Define a new series and explicit compatibility/migration policy before publishing breaking runtime or data changes. Do not present historical 0.x numbering as a promise of strict Semantic Versioning.

## Release requirements

1. Review the source changes and all public artifacts for private information and credentials.
2. Run release metadata checks and relevant behavioral tests in the applicable runtime. The metadata CI job is not an application compatibility test.
3. Build a minimal application archive from an explicit file manifest, retaining required libraries, compiled frontend assets, templates, version/changelog files, and license notices. Runtime requirements must be established before excluding files.
4. Publish checksums and an immutable release record. A checksum provides integrity checking; it is not independent proof of authenticity. Define trusted release provenance separately.
5. The planned updater selects published stable releases, stages and validates downloads, rejects unsafe archive entries, and records the installed release only after a successful health check.
6. Define recovery for both application selection and database migrations. Generic recovery procedures may be public; actual backup locations, contents, and status remain private.
7. Test upgrades, failed downloads, failed starts, rollback, and restart persistence using isolated test data before claiming compatibility.

The current updater reads a branch version file and overwrites application files from an archive. It does not yet meet these release requirements. No automated deployment is enabled by this policy.

## Repository cleanup

Removed unsupported Windows distribution build files, retired Travis configuration, and the old Ubuntu Xenial Dockerfile/Compose example. That Dockerfile was not a LinuxServer image recipe and referenced missing certificate/key inputs. A reproducible image recipe must be introduced and tested separately.

Retain runtime code, bundled libraries and notices, tests, fixtures, compiled frontend assets, frontend source/build inputs, and Linux service examples until their dependencies and release relevance have been assessed. Remove or modernize them through focused changes with validation, rather than treating age as proof they are unnecessary. Existing Windows-specific updater branches remain pending that assessment.

## Work tracking

GitHub's default labels describe issue type; there is no required universal roadmap label. Prefer bug, enhancement, documentation, and question, adding narrowly useful area labels only as work requires them.

Use issues for concrete work with acceptance criteria, pull requests for implementation, milestones for intended releases, and a Project status field for Backlog, Ready, In progress, and Done. A roadmap label is optional for a small number of umbrella issues; a planned label is unnecessary when status already records scheduling. An issue can be both a roadmap item and an enhancement if those labels add useful information.

## Proposed roadmap

1. Establish regression coverage and release packaging for the legacy runtime, then ship focused fixes in the existing numeric version series.
2. Implement verified application-release updates and recovery for the legacy-image distribution path.
3. Inventory and pin bundled/backend/frontend dependencies; remove unsupported platform code and unused distribution files only after checking references and behavior.
4. Define and test the Debian host/Docker/architecture compatibility matrix. Mark untested targets explicitly.
5. Prototype a reproducible independently built image, drawing on licensed LinuxServer image/baseimage sources and preserving required behavior. Pin base image inputs and separate image revisions from application versions.
6. Evaluate porting the application and dependencies to a supported Python 3 runtime. Specify API, configuration, database, and frontend compatibility before implementation.
7. Evaluate Rust in a separate design proposal or prototype with compatibility tests and measurements. A rewrite is not the default implementation plan and should not block maintenance releases.

These are proposed work items, not claims of completed functionality. Create issues and milestones when the corresponding scope is accepted; a full GitHub Project is optional for a small backlog.

## Source history

See source-provenance.md for the imported version and commit. Preserve the original Git history and licensing. Public provenance must not contain local paths or deployment observations.
