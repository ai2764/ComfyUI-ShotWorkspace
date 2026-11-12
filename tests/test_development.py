import ast
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planning import PlanningService, director_rules, validate_plan

ROOT = Path(__file__).resolve().parents[1]

class CandidateClient:
    def __init__(self, candidate=None):
        self.candidate = candidate if candidate is not None else {'title': 'The missing key', 'script': 'Alex finds a key.\nTao [English]: Where did you find that?'}
        self.calls = []
    def complete_json(self, stage, system, payload, **kwargs):
        self.calls.append((stage, system, payload, kwargs))
        return {'value': kwargs['validate'](self.candidate), 'timing': {'stage': stage, 'total_ms': 12}}

class DevelopmentTests(unittest.TestCase):
    def test_develop_returns_editable_script_with_new_dialogue_and_receipts(self):
        client = CandidateClient()
        result = PlanningService(client).develop({'idea': 'Alex and Jordan discover a mysterious key.', 'config': {'secret': 'excluded'}})
        self.assertEqual(result['script'], client.candidate['script'])
        self.assertEqual(result['title'], 'The missing key')
        self.assertEqual(result['timing']['total_ms'], 12)
        self.assertEqual(result['rule_manifest']['stage'], 'script_develop')
        stage, system, payload, options = client.calls[0]
        self.assertEqual(stage, 'script_develop')
        self.assertEqual(payload, {'idea': 'Alex and Jordan discover a mysterious key.',
            'target_duration_s': 40, 'max_script_words': 300, 'max_english_dialogue_words': 60})
        self.assertLessEqual(options['max_tokens'], 3000)
        self.assertIn('premise', system.lower())
        self.assertIn('dialogue', system.lower())

    def test_rejects_empty_or_oversized_ideas_before_request(self):
        for idea in ['', ' ', 'x' * 4001, None, []]:
            client = CandidateClient()
            with self.subTest(idea=type(idea)), self.assertRaises(ValueError):
                PlanningService(client).develop({'idea': idea})
            self.assertEqual(client.calls, [])

    def test_rejects_invalid_or_unbounded_script_drafts(self):
        for candidate in [[], {}, {'title': 'x', 'script': ''}, {'title': 'x'*161, 'script': 'x'}, {'title': 'x', 'script': 'x'*16001}]:
            with self.subTest(candidate=str(candidate)[:60]), self.assertRaises(ValueError):
                PlanningService(CandidateClient(candidate)).develop({'idea': 'A key is found.'})

    def test_rejects_invalid_duration_before_transport(self):
        for duration in [None, True, '40', 0, 4.9, 121, float('nan'), float('inf')]:
            client = CandidateClient()
            with self.subTest(duration=duration), self.assertRaisesRegex(ValueError, 'duration'):
                PlanningService(client).develop({'idea': 'A key is found.', 'target_duration_s': duration})
            self.assertEqual(client.calls, [])

    def test_duration_derives_budgets_and_compact_draft_is_valid(self):
        client = CandidateClient()
        result = PlanningService(client).develop({'idea': 'A key is found.', 'target_duration_s': 20})
        self.assertEqual(result['title'], 'The missing key')
        self.assertEqual(client.calls[0][2]['max_script_words'], 150)
        self.assertEqual(client.calls[0][2]['max_english_dialogue_words'], 30)

    def test_rejects_draft_over_total_word_budget(self):
        client = CandidateClient({'title': 'Too long', 'script': 'action ' * 301})
        with self.assertRaisesRegex(ValueError, 'script word budget'):
            PlanningService(client).develop({'idea': 'A key is found.'})

    def test_rejects_accumulated_english_dialogue_over_budget(self):
        for script in ['Alex [English]: ' + 'word ' * 61,
                       'Alex [English]: ' + 'word ' * 31 + '\nTao [English]: ' + 'word ' * 30]:
            with self.subTest(script=script[:40]), self.assertRaisesRegex(ValueError, 'English dialogue word budget'):
                PlanningService(CandidateClient({'title': 'Too talkative', 'script': script})).develop({'idea': 'A key is found.'})

    def test_english_budget_does_not_claim_other_language_timing(self):
        for language in ['French', 'Chinese']:
            script = 'Alex [' + language + ']: ' + 'word ' * 61
            result = PlanningService(CandidateClient({'title': 'Draft', 'script': script})).develop({'idea': 'A key is found.'})
            self.assertEqual(result['script'], script.strip())

    def test_development_loads_only_shared_selected_profile_and_dialogue(self):
        package = {'profile': 'profiles/ozu.md', 'files': {
            'SKILL.md': '[sources](SOURCES.md)', 'SOURCES.md': 'FORBIDDEN_SOURCE',
            'references/shared.md': 'SHARED [other](../profiles/other.md)',
            'profiles/ozu.md': 'SELECTED [all](../SOURCES.md) [dialogue](../dialogue/ozu.md)',
            'profiles/other.md': 'FORBIDDEN_OTHER', 'injection/ozu.md': 'FORBIDDEN_COMPACT',
            'dialogue/ozu.md': 'SELECTED_DIALOGUE', 'dialogue/other.md': 'FORBIDDEN_DIALOGUE'}}
        rules = director_rules('script_develop', package)
        for included in ['SHARED', 'SELECTED', 'SELECTED_DIALOGUE']:
            self.assertIn(included, rules.text)
        for excluded in ['FORBIDDEN_SOURCE', 'FORBIDDEN_OTHER', 'FORBIDDEN_COMPACT', 'FORBIDDEN_DIALOGUE']:
            self.assertNotIn(excluded, rules.text)
        self.assertEqual({f['path'] for f in rules.manifest()['files'] if f['path'].startswith('director/')},
                         {'director/references/shared.md','director/profiles/ozu.md','director/dialogue/ozu.md'})
        del package['files']['dialogue/ozu.md']
        self.assertIn('SELECTED', director_rules('script_develop', package).text)

    def test_legacy_package_and_stage_boundaries(self):
        package = {'files': {'SKILL.md': 'LEGACY_GUIDANCE'}}
        self.assertIn('LEGACY_GUIDANCE', director_rules('script_develop', package).text)
        for stage in ['asset_select', 'asset_analysis', 'prompt_write']:
            with self.assertRaises(ValueError): director_rules(stage, package)

    def test_adjacent_scene_heading_is_recovered_as_exact_source_quote(self):
        action='Alex opens the drawer. Jordan watches.'
        for heading in ['INT. EDITING STUDIO - NIGHT', 'EXT. COURTYARD - DAY']:
            script=heading+'\n\n'+action
            candidate={'shots':[{'shot_key':'a','title':'Drawer','brief':action,
                'duration_s':5,'source_excerpt':action,'dialogue_lines':[]}]}
            result=validate_plan(candidate,script)
            self.assertEqual(result['shots'][0]['source_excerpt'],script)
            self.assertEqual(result['shots'][0]['brief'],action)

    def test_scene_heading_recovery_cannot_cover_omitted_narrative(self):
        action='Alex opens the drawer. Jordan watches.'
        script='INT. EDITING STUDIO - NIGHT\nMia hides the key.\n\n'+action
        candidate={'shots':[{'shot_key':'a','title':'Drawer','brief':action,
            'duration_s':5,'source_excerpt':action,'dialogue_lines':[]}]}
        with self.assertRaisesRegex(ValueError,'complete script'):
            validate_plan(candidate,script)

    def test_dynamic_route_dispatches_develop(self):
        tree = ast.parse((ROOT/'routes.py').read_text(encoding='utf-8-sig'))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'author')
        client = CandidateClient()
        namespace = {'AuthoringService': lambda c: SimpleNamespace(client=c), 'LLMClient': lambda *a: client,
                     'store_root': lambda: ROOT, 'PlanningService': PlanningService}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'routes.py', 'exec'), namespace)
        result = namespace['author']({'config': {}, 'idea': 'Alex finds a key.'}, 'develop')
        self.assertEqual(result['title'], 'The missing key')
        self.assertIn("@routes.post('/shot-workspace/llm/{operation}')", (ROOT/'routes.py').read_text())

if __name__ == '__main__': unittest.main()
