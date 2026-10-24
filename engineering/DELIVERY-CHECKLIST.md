# Delivery checklist and cost controls

Read this once at delivery start. Use PROTOCOL.md for the complete evidence contract, not repeated conversation history.

## One-time onboarding, separate from daily delivery

- Verify the actual repository/default branch, authenticated API permissions, merge capability and available server rules. Record agent-verified when protection is unavailable; no purchase/public conversion is required for that mode.
- Establish an initialized checkout from the actual remote main commit. Preserve unrelated work in the primary folder; use an isolated checkout when its Git history is unborn or divergent. Verify imported Git objects by their exact SHA if a connector supplies the baseline. Do not reuse the consumed reconstructed-root exception for subsequent PRs.
- Verify required tool versions, commands and a real scanner consumer against representative current input. Check official supported fixes before introducing a custom adapter. An installation/version string alone is not an interoperability test.
- Record onboarding evidence and invalidate the affected portion after tool/profile/credential/capability changes. The first real PR must still pass all mandatory gates. Later PRs review their complete main-to-feature diff, not the original application import.

## Daily delivery

1. Resume the open PR's ledger, or start a new ledger for a new branch/delivery after the old PR is closed. Controls persist separately in `.engineering/controls/<delivery-id>.json`; retain prior plans. Save requirements. Default repair limit remains two; record any explicit finite exception without resetting history. If main advances, use `delivery.py advance-base` after fetching/merging the verified new main; a fresh snapshot and `control.py bind` consume only that ledger's recorded ancestry-verified transition, preserving its deadline, phase history and failure history.
2. Finish intended edits. Run diff checks, engineering configuration/tests and actual tool availability checks before model reviews. If an external adapter changed, exercise its real consumer and rejection path first. Aggregate observed failures before a repair batch.
3. Freeze with delivery.py snapshot. Create a preflight report from templates/preflight.example.json, populated only from actual command/probe evidence and current base/digest. The template deliberately starts NOT_RUN. It is not passing evidence.
4. Run `python engineering/control.py bind --preflight .engineering/preflight.json`. It checks the fetched origin/main ancestry, required logs and probe fields, and starts one 120-minute total budget. Binding another candidate does not reset the deadline or failure history.
5. Before each costly action run `python engineering/control.py reserve --phase <phase>`. Phases: code-review, security-review, local-checks and remote-review-request. Each can be reserved once per exact candidate. Reserve before dispatch, not after success. An interrupted reservation is not permission to relaunch silently. Diagnose it and preserve its record.
6. Obtain distinct fresh independent code/security reviews for HIGH-RISK, run local verification, then gate/index/commit checks. The gate rejects absent control/preflight/reservation evidence. Same-content results are reused; changed content needs current-candidate reports. All five current project CI jobs remain mandatory.
7. Submit/update one PR. Reserve its one remote review request before sending it. Observe CI and review concurrently, then verify fresh exact-head/rule/provenance evidence and run automerge.py. Only ELIGIBLE permits expected-head Squash. Verify main SHA/tree after merge.

## Failures and stop conditions

- Save actual logs first; distinguish service/download failures, configuration/protocol/tool-version failures and product defects. Use templates/failure-report.md. A green diagnostic is not a completed vulnerability scan.
- Record a stable root-cause fingerprint with `control.py failure --fingerprint <cause-id> --cause <diagnosis> --evidence <saved-file>`. Two occurrences block costly phases. Changing the wording of the same cause must not create a new fingerprint.
- A repeated cause requires an actual changed strategy and a passing current-candidate probe: `control.py strategy --fingerprint <cause-id> --strategy <change> --evidence <probe.json>`. Probe fields: status PASS, complete true, current base and digest. A changed candidate requires a fresh probe. This never replenishes the repair or time budget.
- At two repairs or total expiry, stop and provide cause, verified/unfinished work, concrete next strategy, evidence and remaining authorization. Do not make repeated incremental extension requests the normal workflow. No reduced assertions/scans/thresholds, hidden failures or manual merging.

## Waiting without repeated model work

Preferred when authorized API credentials are available: `python engineering/watch.py --repository OWNER/REPO --pr N --head SHA`. GITHUB_TOKEN is supplied through the host environment only; never extract connector credentials or print/save a token. The script polls without model calls, uses the existing deadline, serializes observers and exits on terminal status. It does not review code, verify all merge provenance or authorize a merge. A host must deliver its terminal result to the agent; no webhook/callback is assumed installed.

Connector-only fallback for this private repository: fetch one compact snapshot, then use bounded quiet heartbeat follow-up at the configured 30-minute interval. The same observer can evaluate a saved authenticated snapshot with `--snapshot <json> --head SHA`. Pending stays quiet, terminal changes notify once, missing/skipped/stale/ambiguous results never pass. Expiry is the earlier of the control deadline and follow-up limit. Delete monitoring on merged/closed/failed/expired state.

This checkout has no provisioned standalone GitHub token or event callback. Therefore script transport is provided and tested, but connector follow-up remains the active fallback. Do not describe that fallback as event-driven or zero-token waiting.

## Reporting and reuse

- Keep one compact state: repository/PR/head/digest/base/ledger/phase receipts/run/review/blocker/next action/deadline. Retain full raw evidence in ignored local storage; show only relevant sanitized excerpts, at most4000 characters per update. Complete review inputs are files, never truncated to meet an excerpt budget.
- Report actual costly-phase counts and elapsed time. Token consumption is unavailable unless a trusted meter supplies it; record unknown rather than fabricate an exact number.
- Common core: frozen evidence, bounded effort, observation and exact-head merge. Project adapter: commands, tools, scanners, sensitive paths and CI. templates/project-profile.example.json is a migration starting point, disabled by default. The Android validator/automerge required-job set is not a universal adapter; adapt and verify it before another project uses it.
