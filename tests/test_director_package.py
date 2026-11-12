import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from planning import director_rules
from tools.build_director_packets import packet


class DirectorPackageTests(unittest.TestCase):
    def test_each_profile_loads_only_its_matching_runtime_packet(self):
        root=ROOT/'authoring/skills/director-style'
        files={p.relative_to(root).as_posix():p.read_text(encoding='utf8') for p in root.rglob('*.md')}
        self.assertLess(sum(len(s.encode()) for s in files.values()),262144)
        shared=files['references/shared.md']
        for profile in ['baseline','anderson','wilder','coen','fincher','ozu']:
            with self.subTest(profile=profile):
                path=f'profiles/{profile}.md'
                self.assertEqual(files[f'injection/{profile}.md'],packet(shared,files[path]))
                package={'files':files,'entrypoint':'SKILL.md','profile':path}
                plan=director_rules('script_plan',package)
                refine=director_rules('description_refine',package)
                self.assertEqual([p for p,_ in plan.files if p.startswith('director/')],[f'director/injection/{profile}.md'])
                self.assertEqual([p for p,_ in refine.files if p.startswith('director/')],['director/references/shared.md',f'director/{path}'])
                self.assertLess(len(plan.text),48000)


if __name__=='__main__':unittest.main()
