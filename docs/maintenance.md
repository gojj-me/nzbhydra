# Maintenance and release policy

This document describes public project policy. Machine-specific instructions, personal workflows, deployment details, incident records, and credentials do not belong here.

## Scope and compatibility

Maintain the original NZBHydra v1 application, with Linux containers as the supported distribution target. Native Windows and macOS packaging are outside scope; development tools may run on other systems.

Debian 10, 11, 12, and 13 are requested Docker host compatibility targets, not a claim that the application or Docker vendor currently supports every version. A host runs the Docker engine and kernel; the image supplies the application runtime and userspace. Compatibility must be tested against the specific architecture, kernel, Docker version, storage, permissions, networking, and image. Do not publish a support claim before verifying that combination. Older hosts require a separately documented legacy compatibility policy.

Keep the legacy-image application update path available. An independently built image is a later distribution option, not a prerequisite for fixing the existing application. No replacement image or runtime migration is implemented by this documentation.

## Versioning and changelog

- version.txt is the authoritative application version. The imported baseline is 0.2.233.
- The next application release is 0.3.0. Continue with 0.3.1, 0.3.2, and subsequent 0.3.x releases until the maintainer explicitly chooses to start 0.4.0. Do not create a 0.2.234 release.
- Preserve changelog.md, its separator, its descending `### <version>` headings, and its existing Added/Changed/Fixed wording. The application's changelog reader depends on this structure.
- At release preparation, add the new version section at the top of the existing version entries and update version.txt in the same change. Do not add an Unreleased heading that changes the first version heading consumed by the legacy reader.
- Documentation-only changes do not advance the application version. Track unfinished work in issues and release milestones, not as completed changelog entries.
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

Use [GitHub issues](https://github.com/gojj-me/nzbhydra/issues) for concrete tasks with acceptance criteria and [milestones](https://github.com/gojj-me/nzbhydra/milestones) for intended releases. These are the source of truth for scope and progress; do not duplicate the backlog in this document.

The next release is tracked by the [0.3.0 milestone](https://github.com/gojj-me/nzbhydra/milestone/1). Issues use bug for confirmed defects, enhancement for improvements, documentation for documentation work, and question for undecided proposals. Labels describe the work; the milestone schedules it. Do not invent bug reports before a defect has been identified and reproduced.

Future work remains in issues without a milestone until selected for a release. Separate roadmap/planned labels or a Project board are not required. Add a board only if the backlog needs more detailed workflow tracking.

The [runtime modernization comparison](https://github.com/gojj-me/nzbhydra/issues/6) and [independent container build](https://github.com/gojj-me/nzbhydra/issues/7) are unscheduled. Neither a Python 3 port nor a Rust rewrite has been selected. Preserve observable behavior and assess dependency work, implementation effort, maintenance burden, and measured performance before choosing.

## Source history

See source-provenance.md for the imported version and commit. Preserve the original Git history and licensing. Public provenance must not contain local paths or deployment observations.
