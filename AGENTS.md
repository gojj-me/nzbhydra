# AGENTS.md

A concise guide for AI coding agents working on this repository. It complements `README.md` with machine-actionable build, test, run, and convention notes.

## This repository is public

Everything committed here is world-readable and permanent — source, comments, tests, docs, commit messages, PR titles and descriptions, issue text. A later fix does not retract what has already been cloned, cached or indexed. This file is public too, and is bound by its own rules.

Using an internal source to get the behaviour right is fine; publishing it is not. Only the externally observable result belongs in the repo.

- **Never name private repositories or services.** `desksdkgo`, `twapi-go-sdk` and the MCP SDK are public and may be cited freely. The backends behind the Projects and Desk APIs are not — do not name their repositories, packages, files, handlers, models, or query-argument identifiers. Describe the HTTP endpoint instead: route, parameters, JSON keys, status codes.
- **Never name internal infrastructure.** Deployments, hostnames, dashboards, monitoring, CI tooling, chat channels, wikis, runbooks, or environment detail beyond the documented `TW_MCP_ENV` values.
- **Never reference internal tracking.** Ticket keys, incident IDs, or links and commit hashes in private repositories. Public protocol references (`SEP-2575`) are fine — those are published.
- **Never describe a backend defect as a defect.** State what the endpoint does today ("list endpoints clamp `pageSize` over 100 to 100"), not that it is a bug, what causes it, or when it is due to be fixed — the service is still running the old code.
- **Never publish unreleased information.** Roadmap items, planned deprecations, dated fixes, feature flags, or capacity and traffic figures.
- **Never commit real data.** Tokens, API keys, cookies, real installation subdomains, or real customer and employee names, emails and IDs — in code, tests, fixtures, log samples and error strings alike. Fixtures use `example.com`, `test.teamwork.com`, `john@example.com`, and IDs like `777`/`12345`.

| Instead of                                          | Write                                                        |
|-----------------------------------------------------|--------------------------------------------------------------|
| "bound by `Model.UnmarshalParam` in `<private repo>`" | "the endpoint parses `YYYY-MM-DD` only, and 400s otherwise"   |
| "clamped in the backend's request-defaults helper"   | "list endpoints clamp `pageSize` over 100 to 100"            |
| "broken until the next backend release"              | "returns 422 in this case"                                   |
| "see PROJ-1234"                                      | omit, or describe the behaviour the change addresses         |
| a real site URL in a test                            | `https://test.domain.tld`                                  |

Commit messages and PR descriptions follow the same rules: what the change does and why, in terms of the public API and this server's own behaviour. No internal links, no ticket keys, no "as discussed in <channel>", no private reviewer names. Before committing, re-read the diff as an outsider would and drop any line that only makes sense to someone with access to private systems — the code ships, the reference does not.

# Project instructions

Read docs/maintenance.md for scope, versioning, release requirements, and milestone-based work tracking.

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
- Apply the privacy rules below to issue bodies, comments, relationships, pull requests, and release notes as well as tracked files.

## Privacy
- Public files must contain reusable project information, not personal computer layouts, customer details, infrastructure inventories, deployment records, backup status, or assistant conversations.
- Never commit passwords, tokens, private keys, recovery codes, cookies, authentication stores, or secret-bearing logs and exports to any Git repository, including private repositories.
- Private repository visibility does not authorize storing arbitrary customer or personal information.
- Store credentials in a credential manager or secret store. Keep non-secret private operational notes outside tracked files; .local/ is ignored but is not a security boundary or a synchronization mechanism.
- Review staged changes and all externally published text for private information. Secret scanners do not detect every privacy issue.
