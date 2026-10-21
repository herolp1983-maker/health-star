"""Report changed sensitive paths without granting PR write access to CI."""
import json
import os
from pathlib import Path
import re
from delivery import ROOT, base_sha, execute, sensitive

event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
base = os.environ.get('BASE_SHA', '')
if re.fullmatch(r'[0-9a-f]{40}', base) and base != '0' * 40:
    base = base_sha(base)
    raw = execute(['git', 'diff', '--name-only', '-z', '--no-renames', base, 'HEAD', '--'])
else:
    # Initial push/workflow dispatch: review all committed paths, never an empty fake pass.
    raw = execute(['git', 'ls-tree', '-r', '--name-only', '-z', 'HEAD'])
paths = sorted(p.decode() for p in raw.split(b'\0') if p)
risk = sensitive(paths)
def literal(value):
    # Paths are untrusted; keep them in a fenced JSON block rather than HTML/Markdown links.
    return json.dumps(value, ensure_ascii=True).replace('`', '\\u0060').replace('<', '\\u003c')
lines = ['## Change risk', '', '**HIGH-RISK** — distinct independent code and security review required before automatic merge.' if risk else 'NORMAL — no configured sensitive paths matched.', '', '```json', literal(risk), '```', '', 'This is a path flag, not a security approval.']
with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
    stream.write('\n'.join(lines) + '\n')
print(f'{"HIGH-RISK" if risk else "NORMAL"}: {len(risk)} sensitive paths in {len(paths)} changes')
