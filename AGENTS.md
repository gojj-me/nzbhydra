# Project instructions

Read docs/maintenance.md for scope, versioning, release requirements, and milestone-based work tracking.

## Development
- Maintain NZBHydra v1. Preserve compatibility with the legacy runtime until an explicitly versioned migration is tested.
- Target Linux containers. Assess future runtime and image changes separately from legacy application fixes.
- Keep fixes focused, preserve source attribution and third-party licenses, and validate behavior before release.
- Do not delete bundled dependencies, frontend build sources, fixtures, or runtime branches merely because they are old. Establish references and verify behavior first.

## Task tracking
- GitHub issues and milestones are the authoritative roadmap, task backlog, and source of task status. Do not maintain a competing task list in documentation or local notes.
- Before starting work, find the relevant issue or create a focused issue with acceptance criteria. Keep its scope, progress, blockers, and milestone current; leave unscheduled work without a milestone.
- Link related issues, dependencies, parent/sub-issues, pull requests, and release references where useful. Record blocking relationships explicitly and avoid duplicate issues.
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
