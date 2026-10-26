# Engineering delivery

This repository contains the production hybrid Android project in `hero-health-android/`, a separate prototype, and design assets. Preserve their existing scoped AGENTS.md instructions. Do not apply prototype UI/runtime requirements to production Android.

- Discover the six engineering skills under `.agents/skills/`. Read `engineering/PROTOCOL.md` for their shared contract and `engineering/project.json` for actual tasks. Scripts run from repository root with Python 3.12+.
- On 2026-10-20 the user explicitly replaced manual merging with fully automatic delivery. “当前功能开发完成，执行完整的工程化交付流程。” invokes `github-delivery` and authorizes commit, feature-branch push, PR creation/update, review requests and automatic Squash merge of the exact verified candidate. Keep unrelated work out. Never bypass checks, push ordinary changes directly to main, use admin overrides, or create a tag during daily delivery.
- `code-review` must use a fresh context, without developer conversation or rationale, and is read-only. A delegated reviewer may inspect source around the frozen diff. No independent reviewer means FAIL, never a self-review PASS.
- Local and CI fixes share ONE persisted budget of two batches for the same delivery. Reserve a batch before editing. Restarting a chat, committing, pushing or moving to CI does not reset it. Never weaken original assertions, scans, thresholds, excludes or required checks to produce green results.
- Missing, malformed, stale or incomplete evidence blocks Ready. Reports bind to a base SHA and an exact candidate content digest. A source change invalidates review/check evidence. CI success is insufficient until required rules and latest head are verified.
- Only explicit “执行版本发布” invokes `cut-release`; version changes and tags are excluded from ordinary PRs. Tags require additional explicit authorization.
- The user authorized phase 2 on 2026-10-20 and chose free agent-verified delivery. PR #1 merged on2026-10-24 as d1f803dc05c83948496946cbe24cdebaad87fa51; main now contains the application baseline. Verify current remote main before every new scoped PR. Do not repeat the first import or describe agent checks as GitHub-enforced protection.
- Read engineering/DELIVERY-CHECKLIST.md before costly work. Bind actual preflight and reserve each costly phase with control.py. Same-content reruns, expired total budgets and repeated causes without a changed-strategy probe block the gate. Preserve the original two-batch repair budget and all five current CI jobs. Other projects require their own verified adapter.
- Read `engineering/AUTONOMOUS.md` before merging. Require current independent reviews, local checks, all five real CI jobs, an up-to-date matching PR head/tree and any effective server rules. In agent-verified mode record the absence of server enforcement explicitly. Use the connector's expected_head_sha plus squash, then verify merged=true and the resulting main commit. Do not queue native auto-merge across future unreviewed pushes without a mandatory AI attestation check.
- CI timeout means automatic follow-up, not manual user commands or merging. Prefer the authorized script observer when available; otherwise use bounded connector heartbeat as described in AUTONOMOUS.md. Preserve the ledger and stop on merge/closure/failure or the original control deadline (current default at most two hours).
- WorkBuddy knowledge remains one-way and read-only, following the user's global knowledge instructions. Do not copy personal health records, phone API keys or signing secrets into review inputs or reports.

## Code Review Rules

- Preserve app upgrade identity, encrypted-vault aliases, backup compatibility and atomic restore. A canceled safety export must prevent restore.
- Health records and AI credentials must not reach logs, plaintext fallback storage or unsolicited network requests. AI values enter trends only after user confirmation.
- Check both Java native code and TypeScript bridge/business logic. Assess lifecycle, concurrency, resource cleanup and rejection paths; tests and lint alone do not prove those properties.
