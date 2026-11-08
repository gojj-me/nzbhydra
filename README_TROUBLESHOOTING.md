# Provider recovery and search outcomes

This guide describes NZBHydra v1's maintained Python 2.7 behavior for the 0.2.300 release line. A target release is not the installed version: check your selected build before relying on its fixes. [Issue #14](https://github.com/gojj-me/nzbhydra/issues/14) owns this guidance; GitHub issues and milestones hold live task status.

## Identify the outcome first

| Observation | Meaning | Next action |
| --- | --- | --- |
| Authentication failure / permanently disabled | Hydra classified the provider response as an authentication or API-access failure | Validate endpoint, credential and account/API entitlement privately, then explicitly re-enable after repair |
| HTTP 429 or recognized request/download-limit response | Provider quota or rate limit; Hydra persists a cooldown | Wait until the next permitted attempt and review the provider's quota rules |
| Connection, TLS or HTTP access failure | Request could not complete successfully | Check endpoint/service availability and the certificate chain; keep certificate and hostname verification enabled |
| Parsing failure | Response did not match the supported adapter contract | Investigate provider response/adapter compatibility; a reachable homepage is insufficient evidence of a working search/download contract |
| Successful search with no matches | That request returned no accepted matches from the successfully searched provider | Check query/category/filters and coverage; do not treat this alone as a broken indexer |
| Provider not selected | Configuration, selection, capability, limit or disablement rules excluded it | Check the selection rules below; exclusion alone is not a provider failure |
| Database unavailable / controlled HTTP 503 | Application persistence could not complete within its limits | Treat the request as failed/unavailable, not a successful empty search; investigate application/database state separately |

A provider message is evidence of its response, not a complete diagnosis. For example, the adapter maps recognized Newznab error 100 to “The API key seems to be incorrect,” 101 to account suspension and 102 to API access not allowed. The first message does not prove a typing mistake: the endpoint, account or API entitlement may also be wrong. A working website login does not establish API access. HTTP 200 alone does not establish authenticated search success because a provider can return an error inside the body.

## Recover from authentication disablement

1. In a private session, check the provider's official API instructions and account page. Confirm the supported HTTPS API endpoint, current API key, account status and API/search entitlement. Use the provider's own account tools to check quotas and restrictions.
2. In Hydra's indexer configuration, correct the endpoint/credential as needed and save it. Avoid putting a key into a shell command, browser address bar, screenshot or shared URL. If using Hydra's connection test, perform one deliberate test after checking the details; it contacts the provider and may count against a quota. A successful probe is not proof that every search/download operation is permitted.
3. Open **History & Stats → Indexer statuses**, the tab alongside Search history, Download history and Stats. On the affected row, use the check-mark control in **Disabled until**; its tooltip is **“Click to enable the indexer again.”** Access requires permission to view/manage statistics under the instance's authentication settings. The control clears recorded failure/disablement state; it does not repair credentials or turn on a configuration-disabled indexer.
4. Confirm the indexer is enabled in configuration and permitted for the intended search type. Make one small controlled search and inspect its per-indexer outcome. If authentication fails again, stop repeating attempts and resolve the provider/account issue privately.

Permanent authentication disablement persists in the database. Saving settings, restarting the application, a concurrent successful response or enabling **Ignore temporarily disabled** does not clear it. Explicit re-enablement is required after repair; [#9](https://github.com/gojj-me/nzbhydra/issues/9) supplies that behavior. Do not edit the database or recreate the container as a credential-recovery procedure.

## Respect temporary cooldowns

[#10](https://github.com/gojj-me/nzbhydra/issues/10) handles HTTP 429 and recognized Newznab request/download-limit responses. A valid `Retry-After` supplies the next attempt time. Missing, malformed or past values use a 15-minute fallback; zero delay has a minimum one-second cooldown. The fallback is an application policy, not a claim about the provider's actual reset schedule.

Active rate-limit cooldowns survive restart and block shared indexer search/access requests even when **Ignore temporarily disabled** is enabled. Expiry makes a subsequent request eligible; it does not schedule a request or guarantee restored quota. Ordinary temporary access failures use their own escalating backoff. Configuration/capability probes and requests outside the shared search/access path are not all covered by this cooldown mechanism.

The explicit enable control clears temporary state too, including a recorded cooldown. **Do not use it or repeated connection tests to bypass provider limits.** Wait for the deadline and check entitlement/quota privately if limits recur. Do not assume that a general temporary-disable override authorizes ignoring provider restrictions.

## Understand provider selection

**Internal searches** are searches made through Hydra's web interface. **API searches** are external clients using Hydra's API. Each indexer's **Enable for...** setting permits internal only, API only or both. A provider can legitimately participate in one and be excluded from the other. Inspect the configured access setting and request origin; a short exclusion label alone is not a complete diagnosis.

Other selection rules include the configuration-enabled switch, explicit provider selection, category restrictions, query/identifier capabilities, configured hit/download limits, API load limiting, permanent authentication disablement and temporary cooldowns. A selected checkbox does not override those eligibility rules. In the results view, provider checkboxes can also hide already returned results; hiding results is different from making a provider request.

## Interpret empty and partial results

Expand **Indexer statuses / Rejected results** in the search results view. Check whether each participating provider searched, whether it succeeded, and which results Hydra rejected through configured restrictions. Separately review configured or temporarily excluded providers. A completed HTTP/API request, duplicate removal, identifier conversion or “All indexers exhausted” message does not establish that every configured provider searched successfully. Exhaustion concerns the selected search's remaining work, not universal provider availability or completeness.

Synthetic example:

- **Example Alpha** searched successfully and returned no matches.
- **Example Beta** is permanently disabled after an authentication failure.
- **Example Gamma** is waiting for a rate-limit deadline.

The combined output may contain zero results, but only Alpha supplied a healthy no-match response. It is an incomplete search across those three configured providers. Repair Beta privately and wait for Gamma before drawing a broader conclusion. If Alpha instead returns results, those results can still be useful while the combined coverage remains partial.

API clients may display only returned items or report “no results” without exposing every failed/skipped provider. A successful response or empty item list therefore does not certify complete coverage. Check Hydra's per-provider status privately when diagnosing missing results. No new API completeness flag or client behavior is introduced by this documentation.

## Share only a minimal synthetic report

If an application defect remains, use the [GitHub issue workflow](https://github.com/gojj-me/nzbhydra/issues). Describe the selected public source revision, affected operation, expected/actual behavior and a minimal invented response or reproduction. Distinguish a confirmed defect from an unverified provider diagnosis. Keep task status on the issue rather than maintaining a separate troubleshooting backlog.

Do not publish real settings, keys, cookies, authorization headers, full query/download URLs, account labels, search histories, databases, raw logs or debug bundles. Redaction handles recognized credential formats; it is not a privacy guarantee. Review the whole report, not just the key field. Never disable TLS verification as a workaround.

For application deployment/recovery, use [README_DEPLOYMENT.md](README_DEPLOYMENT.md). For synthetic behavioral checks and their limits, use [README_TESTING.md](README_TESTING.md). Provider compatibility limits, including the retained but currently unsupported NZBClub adapter, are recorded in the [maintenance policy](docs/maintenance.md#nzbclub-tls-and-feed-investigation).
