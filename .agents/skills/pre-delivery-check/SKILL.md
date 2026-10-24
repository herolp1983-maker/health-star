---
name: pre-delivery-check
description: Verify current independent reviews and run local JVM tests, web tests/build and Android lint/debug build before a PR.
---

# pre-delivery-check

Read engineering/PROTOCOL.md and project.json.
Input: frozen base/candidate and completed code-review.json/security-review.json.

1. Run python engineering/delivery.py gate to reject absent, stale or incomplete reviews and Critical/High findings.
2. On Windows run pwsh -NoProfile -File engineering/check-local.ps1. It prepares bundled web assets then runs testDebugUnitTest, lintDebug and assembleDebug in an owned ASCII staging workspace without copying release secrets. On Linux run npm ci, npm test and npm run build:web in hero-health-android, then ./gradlew --no-daemon --console=plain :app:testDebugUnitTest :app:lintDebug :app:assembleDebug. Check all exit codes. No connectedAndroidTest.
3. Run python engineering/validate.py for workflow/skill schema checks and python -m unittest discover -s engineering/tests for engineering invariants.
4. Inspect diff --check and exact intended staged files, preserving original assertions, version numbers, production settings and existing scoped instructions. Fail on staged secrets, private health records, generated assets, APKs, signing material or temporary evidence. Run the candidate/review gate again after checks to catch source changes.
5. Write pre-delivery.json with base, candidate digest, complete=true, PASS/FAIL, evidence paths and limitations. Its checks array must contain actual domain-tests, web-build, android-debug, engineering-config and engineering-tests command results with name/exit_code. Do not omit failed commands or mark complete if anything mandatory was skipped. Never report Ready from build success when reviews failed or were unavailable.

Output: unified PASS/FAIL and failed commands/reasons. Does not bump versions, sign releases, commit or push. Aggregate repair candidates; github-delivery owns the shared two-batch budget.
