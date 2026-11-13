"""Package exactly the verified Skill release inventory."""
from pathlib import Path
import runpy
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        root = Path(self.root)
        release = runpy.run_path(str(root / 'tools/skill_release.py'))['check']()
        if self.target_name == 'wheel':
            source = root / '.agents/skills/cirdc-research'
            for name in [*release['files'], 'version.json']:
                build_data['force_include'][str(source / name)] = 'cirdc/web/agent_instructions/' + name
