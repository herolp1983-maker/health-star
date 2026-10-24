# Fully automatic delivery

The user changed the policy on 2026-10-20: Codex develops, independently reviews, fixes, submits the PR, verifies gates and automatically Squash merges. No manual Merge click is required. Failure means BLOCKED, not automatic approval. This supersedes earlier manual-merge wording, including the historical phase-1 report.

## Mode and boundaries

Use `automatic-squash-exact-head`, through the GitHub connector merge_pull_request with **expected_head_sha** and **merge_method=squash**. Before that call, generate an ELIGIBLE plan with `python engineering/automerge.py --remote <json> --rules <json> --commit <reviewed-local-head>`. For the initial README bootstrap only, if the reviewed local root commit has the same tree but a different SHA from GitHub's root commit, pass `--remote-commit <uploaded-PR-head>` and verify both root trees plus the uploaded head tree from GitHub evidence. The script does not obtain credentials or merge by itself; it validates the exact tool arguments the orchestrating Codex is authorized to use. The connector/GitHub rechecks the expected head server-side.

Require the following, without a human code-review gate:

- The exact current candidate passes both local reviews and pre-delivery checks; commit tree equals the reviewed manifest.
- For HIGH-RISK, code and security reviewers are distinct fresh contexts. HIGH-RISK never automatically requests user review or hand merging.
- The current non-draft PR belongs to the configured repository, targets main and has the reviewed head SHA. All five mandatory jobs must be real GitHub Actions results for that head, completed SUCCESS. Missing/skipped/neutral/cancelled jobs do not pass. Existing P0/P1/Critical/High AI findings block merging.
- In `server-enforced` mode, effective main rules require a PR, all five checks, strict up-to-date behavior, no approving human reviews, and no bypass actors. In the explicitly selected `agent-verified` mode, Codex checks the same five real Actions results and current base/head before the exact-head merge API call. This does not protect main against other writers or out-of-band merges; report that limitation clearly. Never portray an unenforced ruleset as active.
- Re-read PR head/checks/rules immediately before merge. Rejected expected SHA or strict-base condition means restart verification, never retry with a new head without re-review. Verify the resulting PR merged flag, merge SHA and main ancestry/tree afterward before reporting MERGED.
- The reviewed manifest base must equal the current verified PR target base, except for the one-time reconstructed-root case: both commits must have no parents and identical verified Git trees. The uploaded PR head tree must equal the reviewed local commit tree. Reviewing only the last feature commit cannot authorize the whole PR. If main advances, fetch/update the feature branch, run `python engineering/delivery.py advance-base --base <fetched-main-SHA> --reason "main advanced"` without resetting ledger identity/repair count, and take a new full snapshot/review/check cycle. The helper verifies ancestry and the fetched origin/main ref. Conflict or defect repairs consume the same remaining repair budget.

Native GitHub Auto-merge is optional. Do NOT arm a native queued merge based only on passing local AI review: a subsequent push may preserve the queued merge while invalidating that review. Only a verifiable head-bound required AI attestation check would make that mode acceptable. The current integration has not established such a check. Exact-head agent merging avoids this stale-review race and still requires no human merge.

Daily delivery does not grant authorization for version releases, tags, production deployment, public APK distribution, changing repository visibility or buying a GitHub subscription. Release requests still enter cut-release explicitly, but their passing PRs also merge automatically.

## Normalized evidence contract

Evidence is local JSON under .engineering and must be populated from real authenticated GitHub responses/UI, not generated from expected results. Never accept evidence bundled in an untrusted PR as authoritative. The same agent that gathered it records fetched_at as a Unix UTC timestamp.

Remote JSON fields:

`repository`, `pr_number`, `state` (OPEN), `draft` (false), `base_branch`, `head_sha`, `head_tree_sha`, `head_tree_verified` (true), `base_sha`, `current_base_sha`, `up_to_date` (true), `candidate_digest`, `fetched_at`, `checks`, `unresolved_blocking_findings` (0), `fix_rounds` (normally 0..2; a higher finite maximum only for an explicitly user-authorized exception bound to the delivery ledger). For a distinct reconstructed root baseline, also record `base_tree_sha`, `base_tree_verified` (true) and `base_parent_count` (0), derived from authenticated GitHub commit/file evidence.

Each check has `name`, `head_sha`, `status` (COMPLETED), `conclusion` (SUCCESS), `app_slug` (github-actions), `workflow_path` (.github/workflows/engineering.yml). Obtain the workflow path/provenance from actual run/check metadata; do not fill it merely because the job name matches. Preserve raw response references locally for audit. Fresh remote metadata is at most 60 seconds old at authorization.

Rules JSON fields:

`repository`, `branch`, `verified`, `enforced`, `pull_request_required`, `strict`, `required_approving_reviews` (0), `bypass_actors` ([]), `required_checks`, `required_check_sources`, `fetched_at`, `source` (github-api or authenticated-github-ui). In `server-enforced` mode, all five checks must be listed with github-actions sources. In `agent-verified` mode, use `enforced:false`, `server_enforcement_unavailable:true`, `pull_request_required:false`, `strict:false`, `required_checks:[]`, `required_check_sources:{}`. Rule metadata is at most five minutes old. Preserve stronger actually enforced checks if account capability changes.

pre-delivery.json is bound to candidate base/digest with `complete: true`, `status: PASS` and `checks` containing domain-tests, web-build, android-debug, engineering-config and engineering-tests with exit_code 0. Every reported command must succeed; a headline PASS cannot contradict a failed command. Build logs alone are insufficient. The plan also loads the two review reports and validates them with delivery.py.

## Bounded observation after eight minutes

When authorized GITHUB_TOKEN and a host completion callback are actually provisioned, engineering/watch.py can poll without model calls. It never merges. Its terminal result must return to the agent for fresh gate verification. Connector credentials must not be extracted. No standalone token/callback is configured here, so the supported active fallback remains quiet30-minute connector follow-up; do not claim event-driven or zero-token waiting. Both modes use the same control deadline, never a newly calculated extension. See DELIVERY-CHECKLIST.md.

If a real PR is still waiting after the foreground wait budget and standalone script transport is unavailable, use the Codex app heartbeat automation tool to create/update a follow-up in THIS chat at the configured follow_up_minutes interval (currently thirty minutes). Search the task's existing automations first; do not create duplicates. Store PR/repository, delivery ledger ID, expected head, candidate paths, used fix batches and the original control deadline (current maximum two hours). The heartbeat must:

1. Stay quiet on unchanged/non-actionable state. Notify only on merge, blocking failure, expiry or needed account action.
2. Fetch fresh head/check/rule data. Resume the same shared two-batch repair ledger; chat restarts or CI retries do not reset it.
3. If the head changed, invalidate old local evidence; rerun independent reviews/checks before any automatic merge. Never assume an external push was reviewed.
4. Generate the merge plan, perform the exact-head Squash API merge if ELIGIBLE, verify actual merged state, then pause/delete this monitor. Closed PRs also terminate monitoring. Failure after the persisted authorized repair limit, unavailable gates, failed auth or control-deadline expiry reports BLOCKED and stops. Do not silently run indefinitely.

The user has authorized this follow-up as part of their fully automatic delivery request. If scheduling is unavailable, report the concrete limitation; do not claim that a background job exists. Never create an empty monitor before an actual PR exists. Account/payment changes remain the user's responsibility and are not a hand-merge requirement.

## Current free-plan capability

Live GitHub UI on 2026-10-20: Rulesets and classic branch-protection pages state rules will not be enforced on this private repository under the current account; General shows native Allow auto-merge disabled. Codex created the README-only baseline commit `793bef7565415150397eb2c419c730c695119001` on main. The user chose a free automatic path: Codex performs independent review, local checks and real CI verification, then exact-head Squash merging through the API. This is agent-side enforcement, not a server-side guarantee. Do not make the health app public or purchase/upgrade on the user's behalf.

PR #1 completed the first real automatic merge on2026-10-24: d1f803dc05c83948496946cbe24cdebaad87fa51. The README-only bootstrap is historical; future candidates start from actual current main. Current rules/capability must still be verified for every delivery.
