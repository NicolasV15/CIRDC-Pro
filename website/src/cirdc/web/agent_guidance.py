"""Serve the maintained Skill as readable documents, also in installed wheels."""
import json
from pathlib import Path

SKILL_PATH = '/api/agent/v1/skills/cirdc-research'
def guidance_root():
    for base in [Path(__file__).parent / 'agent_instructions',
                 Path(__file__).resolve().parents[3] / '.agents/skills/cirdc-research']:
        if (base / 'version.json').is_file():
            return base
    raise FileNotFoundError('Research guidance is not packaged')


FILES = (*json.loads((guidance_root() / 'version.json').read_text())['files'], 'version.json')


def read_guidance(name='SKILL.md'):
    if name not in FILES:
        raise ValueError('Unknown research guide')
    return (guidance_root() / name).read_text(encoding='utf-8')
