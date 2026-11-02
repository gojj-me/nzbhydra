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

A release requires reviewed public-safe artifacts, matching version/changelog/tag/package metadata, behavioral validation in the applicable runtime, and verified update/recovery behavior. The metadata CI job alone does not establish application compatibility. The current legacy updater does not yet satisfy the target design; no deployment functionality is installed by documentation changes.

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

### Scheduling

Future work remains in issues without a milestone until selected for a release. Separate roadmap/planned labels or a Project board are not required. Add a board only if the backlog needs more detailed workflow tracking.

The [runtime modernization decision](https://github.com/gojj-me/nzbhydra/issues/6) and [new Docker image](https://github.com/gojj-me/nzbhydra/issues/7) both belong to 0.3.0. The image build depends on the runtime decision, and both deliverables must be validated before that release. Neither a Python port nor a Rust rewrite has been selected. Preserve observable behavior and assess dependency work, implementation effort, maintenance burden, and measured performance before choosing.

## Source history

See source-provenance.md for the imported version and commit. Preserve the original Git history and licensing. Public provenance must not contain local paths or deployment observations.
