# Delivery failure diagnosis

- Delivery ID / PR / exact head / candidate digest:
- Actual failed command/job and saved sanitized log:
- Category: external service/download / configuration/protocol/tool version / product defect:
- Stable root-cause fingerprint and prior occurrence count:
- Evidence supporting the cause; remaining uncertainty:
- Official fix/support source checked before custom implementation:
- Consolidated correction or changed strategy; affected paths:
- Real consumer/rejection probe and result; this is not full CI:
- Verified work retained; unfinished mandatory gates:
- Used/authorized repair batches and original history; remaining wall time:
- Costly phases already reserved for this candidate:
- Next action and stop condition; no silent rerun or budget reset:

For two occurrences of the same cause, record failure in control.py and a passing changed-strategy probe before any additional costly phase. Explicit extra repair authorization remains delivery-bound; it does not waive checks or grant unlimited retries.
