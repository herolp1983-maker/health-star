## Risk

NORMAL / **HIGH-RISK** — sensitive files and reasons:

- [ ] Authentication / health records / backup or storage / native bridge
- [ ] AndroidManifest permissions / exported components / network security
- [ ] Crypto / secrets / database migrations
- [ ] CI / engineering policy / review or test configuration

## Change

Problem, resulting behavior and affected areas:

## Validation

- Independent code review: PASS / FAIL — candidate digest:
- Local security review: PASS / FAIL — coverage/limits:
- Domain tests, TypeScript/web build, JVM tests, Android lint/debug build:
- GitHub CI: PASS / FAIL / PENDING — head SHA:
- Codex PR Review: PASS / FINDINGS / PENDING / UNAVAILABLE
- Required branch rules: verified / unknown / unavailable
- Remaining Medium/Low issues:
- [ ] Existing test assertions and mandatory gates were preserved.
- [ ] No signing keys, personal health files, API keys or build products staged.
- [ ] Daily delivery leaves version numbers and tags unchanged.

## Delivery record

ID / branch / base SHA / head SHA / global automatic repair batches used (0–2):

Automatic Squash merge only after all enforced gates and exact-head evidence pass. HIGH-RISK requires independent code AND security review by distinct fresh contexts, rather than a manual user merge.
