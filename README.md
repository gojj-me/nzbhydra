# NZBHydra

NZBHydra v1 maintenance by [gojj-me](https://github.com/gojj-me).

NZBHydra searches multiple NZB indexers from one place and provides a combined indexer endpoint for other applications. This repository maintains the original Python application, targeting Linux containers.

## Development and releases

```sh
git clone https://github.com/gojj-me/nzbhydra.git
cd nzbhydra
```

Read [AGENTS.md](AGENTS.md) for contribution instructions and the [maintenance policy](docs/maintenance.md) for versioning, release requirements, cleanup scope, and milestone-based planning.

The next release is [0.2.300](https://github.com/gojj-me/nzbhydra/milestone/1), followed by further 0.2.x fixes for Python 2.7 within the current Docker image. [0.3.0](https://github.com/gojj-me/nzbhydra/milestone/2) will deliver both a modernized application—Rust or the latest stable Python release available when selected—and a new Docker image. That series will continue as 0.3.x until 0.4.0 is explicitly selected.

The application version is recorded in [version.txt](version.txt); changes for released application versions are recorded in [changelog.md](changelog.md). The legacy application requires Python 2.7.9 or later within the Python 2 series and explicitly rejects Python 3. Future runtime and container changes require separate compatibility work.

## Application deployment

See [README_DEPLOYMENT.md](README_DEPLOYMENT.md) for the persistent application update design, container recreation behavior, test deployments, and recovery. [Issue #3](https://github.com/gojj-me/nzbhydra/issues/3) tracks implementation for 0.2.300; installation is explicit, and maintenance-tool versions are tracked separately from application builds.

## Roadmap and tasks

[GitHub issues](https://github.com/gojj-me/nzbhydra/issues) and [release milestones](https://github.com/gojj-me/nzbhydra/milestones) are the project's roadmap and authoritative record of all tasks and their status. Keep progress and blockers on the relevant issue, link related issues and implementation work, and close issues when completion has been verified. Record why cancelled, superseded, or duplicate work is closed and link its replacement where applicable. Release status is recorded separately from implementation completion. Each substantive task handoff includes a refreshed recommendation for the remaining release work, the next action, and blockers or decisions. The current recommended sequence belongs in the release milestone; remaining gaps must reference issues.

Before creating or restructuring multi-part work, ask the maintainer to choose a checklist in one issue or linked sub-issues, with a concise proposed grouping. Do not select the granularity or split, merge, or convert issues without that decision. Keep the agreed tracking current without repeatedly requesting the same choice. Mark only verified criteria complete, leave partial work open, and report completed/total counts plus remaining work. Percentages describe item counts, not effort; a partially complete issue stays open.

See the [work-tracking policy](docs/maintenance.md#work-tracking) for the full workflow. Documentation explains policy; it does not duplicate the live backlog.

## Source history

Based on [theotherp/nzbhydra](https://github.com/theotherp/nzbhydra), version **0.2.233**, at commit [`526a7c71eeea56ae2e3bc5677c3f9c5da224539f`](https://github.com/theotherp/nzbhydra/commit/526a7c71eeea56ae2e3bc5677c3f9c5da224539f). Original Git history is preserved; see [source provenance](docs/source-provenance.md).

## License and attribution

Original NZBHydra by The other P and its contributors. Distributed under the Apache License, Version 2.0; see [LICENSE](LICENSE). Original copyright and third-party notices remain in their respective files.
