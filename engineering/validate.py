"""Validate skill manifests and fail-closed CI structure (requires PyYAML)."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.engineering-tools/python'))
import yaml

# YAML 1.2-style bools, so GitHub's `on` is not parsed as boolean True.
class Loader(yaml.SafeLoader):
    yaml_implicit_resolvers = {key: [(tag, exp) for tag, exp in values if tag != 'tag:yaml.org,2002:bool'] for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()}
Loader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(?:true|false)$', re.I), list('tTfF'))

def load(path):
    return yaml.load(path.read_text(encoding='utf-8'), Loader=Loader)

def validate():
    expected = {'feature-development', 'code-review', 'security-review', 'pre-delivery-check', 'github-delivery', 'cut-release'}
    found = set()
    for path in (ROOT / '.agents/skills').glob('*/SKILL.md'):
        text = path.read_text(encoding='utf-8')
        if not text.startswith('---\n'):
            raise ValueError(f'Missing frontmatter: {path}')
        _, frontmatter, body = text.split('---', 2)
        info = yaml.load(frontmatter, Loader=Loader)
        name = info.get('name', '')
        if name != path.parent.name or not re.fullmatch(r'[a-z0-9-]{1,63}', name) or not info.get('description') or not body.strip():
            raise ValueError(f'Invalid skill: {path}')
        if 'TODO' in body or '[INSERT' in body:
            raise ValueError(f'Unfinished skill: {path}')
        found.add(name)
    if found != expected:
        raise ValueError('Skill inventory mismatch')
    policy = load(ROOT / '.agents/skills/cut-release/agents/openai.yaml')
    if policy.get('policy', {}).get('allow_implicit_invocation') is not False:
        raise ValueError('Release must be explicit-only')
    config = json.loads((ROOT / 'engineering/project.json').read_text())
    control = config.get('process_control', {})
    if (control.get('required') is not True or control.get('max_costly_phase_runs_per_candidate') != 1
            or type(control.get('max_wall_minutes')) is not int or not 1 <= control['max_wall_minutes'] <= 120
            or control.get('max_log_excerpt_chars') != 4000 or config['max_fix_rounds'] != 2
            or config['follow_up_max_hours'] * 60 > control['max_wall_minutes']
            or not {'engineering/nvd_feed.py', 'engineering/dependency-check.init.gradle', 'engineering/watch.py'} <= set(control.get('compatibility_paths', []))):
        raise ValueError('Delivery cost/control policy missing or relaxed')
    for name in ['DELIVERY-CHECKLIST.md', 'RETROSPECTIVE.md', 'templates/preflight.example.json',
                 'templates/failure-report.md', 'templates/project-profile.example.json']:
        if not (ROOT / 'engineering' / name).is_file():
            raise ValueError('Required closure template missing: ' + name)
    preflight_example = json.loads((ROOT / 'engineering/templates/preflight.example.json').read_text())
    profile_example = json.loads((ROOT / 'engineering/templates/project-profile.example.json').read_text())
    if preflight_example['status'] != 'NOT_RUN' or preflight_example['complete'] is not False or profile_example['ready'] is not False:
        raise ValueError('Templates must not pretend to be passing evidence or an activated adapter')
    workflow = load(ROOT / '.github/workflows/engineering.yml')
    if set(workflow['on']) != {'pull_request', 'push', 'workflow_dispatch'} or workflow['permissions'] != {'contents': 'read'}:
        raise ValueError('Unexpected CI triggers/permissions')
    if set(job['name'] for job in workflow['jobs'].values()) != set(config['required_jobs']):
        raise ValueError('Required jobs mismatch')
    for job in workflow['jobs'].values():
        if 'if' in job or job.get('continue-on-error') or not job.get('timeout-minutes'):
            raise ValueError('Mandatory job can be skipped or unbounded')
        for step in job['steps']:
            if step.get('continue-on-error'):
                raise ValueError('Mandatory failure may be hidden')
            if 'uses' in step and not re.fullmatch(r'[\w./-]+@[0-9a-f]{40}', step['uses']):
                raise ValueError('Unpinned action')
            if 'pull_request_target' in str(step) or '--admin' in str(step):
                raise ValueError('Unsafe CI behavior')
    # Parse all authored YAML plus Gradle wrapper checksum profile.
    for path in (ROOT / 'engineering').glob('*.yml'):
        load(path)
    wrapper = (ROOT / 'hero-health-android/gradle/wrapper/gradle-wrapper.properties').read_text()
    if 'distributionSha256Sum=f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6' not in wrapper:
        raise ValueError('Wrapper distribution hash missing/mismatched')
    if not (ROOT / 'hero-health-android/gradle/wrapper/gradle-wrapper.jar').is_file():
        raise ValueError('Wrapper JAR missing')
    print('PASS: six skills, explicit release policy, YAML, mandatory jobs, SHA pins and wrapper hash')

if __name__ == '__main__':
    validate()
