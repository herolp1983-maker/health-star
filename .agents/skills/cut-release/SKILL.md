---
name: cut-release
description: Prepare an explicitly requested Android version release PR and changelog; excluded from ordinary feature delivery.
---

# cut-release

Trigger only when the user explicitly says “执行版本发布” (or directly invokes this release skill for that purpose). Merely finishing a feature or submitting a daily PR does not authorize a release.
Read engineering/PROTOCOL.md, project.json and scoped AGENTS.md.

Input: intended semantic version/release scope and last verified release baseline. Infer a proposal from verified changes if no version was given; do not invent past release history.

1. Inspect Git/default branch and current app/build.gradle, package.json and package-lock.json version fields. Start a release feature branch such as codex/release-<version>, preserving upgrade identity, signing key references, vault aliases and archive compatibility.
2. Increment versionCode above the existing 4 and any verified released code; use a valid Android versionCode <= 2100000000. Set versionName and package/lock root versions consistently using semantic versioning. Do not select a code already released on another branch.
3. Summarize verified changes since the last actual release tag into CHANGELOG.md. If no tag exists, explicitly state the initial baseline limit.
4. Invoke the same github-delivery reviews, shared repair-budget ledger and checks, clearly indicating that version changes are the purpose of this release PR.
5. The release PR uses the same automatic Squash merge gates as daily delivery. Create a Git tag only if the user separately explicitly authorizes it, and only at the verified merged release commit. Never upload/publish an APK or public release implicitly.

Output: version/code, changelog, validation, PR and actual automatic merge status/SHA. Unknown baseline/version conflict or failed checks blocks release readiness. No signing secrets in CI.
