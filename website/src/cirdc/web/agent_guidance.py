"""Serve the maintained Skill as readable documents, also in installed wheels."""
from pathlib import Path

SKILL_PATH = '/api/agent/v1/skills/cirdc-research'
FILES = ('SKILL.md', 'references/api.md', 'scripts/cirdc_client.py', 'scripts/install_skill.py')


def read_guidance(name='SKILL.md'):
    if name not in FILES:
        raise ValueError('Unknown research guide')
    bases = [Path(__file__).parent / 'agent_instructions',
             Path(__file__).resolve().parents[3] / '.agents/skills/cirdc-research']
    for base in bases:
        path = base / name
        if path.is_file():
            return path.read_text(encoding='utf-8')
    raise FileNotFoundError('Research guidance is not packaged')
