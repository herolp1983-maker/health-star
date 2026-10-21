---
name: security-review
description: Run fast local secret and Android security checks, identify sensitive changed paths and return evidence without modifying source.
---

# security-review

Read engineering/PROTOCOL.md.
Input: frozen candidate manifest/diff and requirements. This is lightweight delivery screening, not an exhaustive security-audit claim.

1. Run python engineering/delivery.py security. It scans candidate files AND exact patch/requirements review inputs (including removed lines) with redacted heuristic secret checks and emits security-static.json. If installed, also run Gitleaks with --redact against the exact review inputs, candidate files AND incremental Git history from frozen base to HEAD, including staging/worktree changes. Check actual local Gitleaks help; current CLI uses git/dir subcommands. Scanner errors block completion. The helper does not claim to replace Gitleaks.
2. Review candidate changes semantically: Manifest permissions/exported components/Intent callers; cleartext and TLS verification; WebView JavaScript plus file access/origin/navigation; sensitive logs; credential/health-record plaintext storage; authorization and consent before health-data transmission; archive encryption and restore safety. Read surrounding Java and TypeScript source where necessary. Match symptoms to reachable code before assigning severity.
3. Run python engineering/delivery.py risk. Manifest, auth, health/backup/storage, native bridge, crypto/key/migration and engineering-policy paths produce HIGH-RISK, with exact paths. Risk is an attention flag, separate from confirmed defects.
4. Write security-review.json using engineering/review.schema.json, with base/digest, reviewer and coverage. List actual tools, unavailable tools and heuristic limits. If Gitleaks is unavailable, heuristic checks PLUS complete semantic review may satisfy this local gate, but explicitly disclose reduced automated coverage; CI must still run Gitleaks.

Known synthetic literal fixtures are adjudicated only by exact path/rule/content fingerprint in engineering/secret-fixtures.json with a concrete reason. Changed literals require fresh review. Never blanket-exclude tests, approve real token/private-key patterns, or change assertions/scanner thresholds to clear findings. Review patch hits (including deleted lines) are not silently covered by a current-source fixture adjudication.

Output: structured findings, tool results and HIGH-RISK paths. No source edits. Any missing mandatory check, incomplete semantic review, scanner failure or unresolved Critical/High means FAIL. Consolidated repairs belong to github-delivery and share its persisted budget.
