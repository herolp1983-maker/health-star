---
name: feature-development
description: Develop a feature in this Android project with focused JVM and web domain tests, staying on a feature branch.
---

# feature-development

Read engineering/PROTOCOL.md and engineering/project.json at repository root, then the scoped AGENTS.md.
Input: user requirements and acceptance criteria; identify the affected native Java and React/TypeScript layers.

1. Inspect git status, default branch and remote. Preserve unrelated work. Create/use codex/<topic>; never develop on main/master. An unborn repository is a setup blocker, not permission to commit its default branch.
2. Implement the agreed change and meaningful regression tests for modified behavior. JVM tests must not require an emulator; include TypeScript domain/bridge tests when affected.
3. Run npm test and npm run build:web in the Android project, then the relevant JVM task through engineering/check-local.ps1 on Windows or the checksum-pinned wrapper on Linux.
4. Report behavior, affected files, test results and remaining issues. Do not increment versions, tag or publish just because development is complete.

Output: reviewable source/test changes and verified test results. On failure preserve the evidence and report the blocker. The two-batch repair limit applies once a delivery ledger has started; development iterations before delivery are not hidden delivery repairs. Hand off to github-delivery only when requested.
