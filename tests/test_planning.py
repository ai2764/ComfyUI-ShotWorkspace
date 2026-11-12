import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planning import load_director_skill, validate_plan, validate_selection, PlanningService
from script_dialogue import source_dialogue

STORY='Alex enters the room. Alex says: "Coffee?" Jordan nods.'

def plan():
    return {'shots':[{'shot_key':'a','title':'Arrival','brief':'Medium shot: Alex enters and asks Jordan for coffee.',
        'duration_s':5,'source_excerpt':STORY,'dialogue_lines':[{'speaker':'Alex','language':'English','text':'Coffee?'}],
        'continuity':{'mode':'off'}}]}

class PlanningTests(unittest.TestCase):
    def test_story_events_and_beats_survive_validation_and_reject_dangling_links(self):
        p=plan()
        p['story_events']=[{'event_key':'e1','source_excerpt':STORY,'participants':'Alex and Jordan',
            'request':'Alex offers coffee.','decision':'Jordan agrees.','action':'Jordan nods.','result':'Both remain in the room.'}]
        p['shots'][0]['dramatic_beat']={'event_keys':['e1'],'start_state':'Alex arrives.',
            'change':'Jordan accepts the offer.','end_state':'Jordan has nodded.',
            'cut_reason':'One shared view shows the offer and response.'}
        result=validate_plan(p,STORY)
        self.assertEqual(result['story_events'],p['story_events'])
        self.assertEqual(result['shots'][0]['dramatic_beat'],p['shots'][0]['dramatic_beat'])
        bad=copy.deepcopy(p);bad['shots'][0]['dramatic_beat']['event_keys']=['missing']
        with self.assertRaisesRegex(ValueError,'event'):validate_plan(bad,STORY)
        bad=copy.deepcopy(p);bad['story_events'][0]['source_excerpt']='Invented source'
        with self.assertRaisesRegex(ValueError,'source'):validate_plan(bad,STORY)

    def test_scene_headers_and_narrative_leadins_are_not_speakers(self):
        self.assertEqual(source_dialogue('SCENE 1\nMia enters the room.'),[])
        self.assertEqual(source_dialogue('SIGN: "OPEN"'),[])
        self.assertEqual(source_dialogue('Then Alex says: "Coffee?"')[0]['speaker'],'Alex')
    def test_skill_references_profile_and_snapshot(self):
        skill={'entrypoint':'SKILL.md','profile':'profiles/quiet.md','files':{'SKILL.md':'Use [rules](references/common.md).',
            'references/common.md':'Preserve the script.', 'profiles/quiet.md':'Hold reactions.', 'profiles/fast.md':'Cut constantly.'}}
        bundle=load_director_skill(skill)
        self.assertIn('Hold reactions',bundle.text)
        self.assertNotIn('Cut constantly',bundle.text)
        self.assertEqual(len(bundle.version),64)
        old=bundle.text;skill['files']['references/common.md']='Changed'
        self.assertEqual(bundle.text,old)
        self.assertNotEqual(bundle.version,load_director_skill(skill).version)

    def test_portable_packets_keep_planning_commands_out_of_description(self):
        from planning import director_rules
        package={'profile':'profiles/ozu.md','files':{'SKILL.md':'[sources](SOURCES.md)',
            'SOURCES.md':'PROVENANCE_NOT_RUNTIME','references/shared.md':'Shared production checks.',
            'profiles/ozu.md':'OZU_SELECTED','profiles/fincher.md':'FINCHER_NOT_SELECTED',
            'injection/ozu.md':'COMPACT_PLAN_PACKET OZU_SELECTED'}}
        planned=director_rules('script_plan',package)
        described=director_rules('description_refine',package)
        self.assertIn('COMPACT_PLAN_PACKET',planned.text)
        self.assertNotIn('COMPACT_PLAN_PACKET',described.text)
        self.assertIn('Shared production checks.',described.text)
        for bundle in [planned,described]:
            self.assertIn('OZU_SELECTED',bundle.text)
            self.assertNotIn('FINCHER_NOT_SELECTED',bundle.text)
            self.assertNotIn('PROVENANCE_NOT_RUNTIME',bundle.text)

    def test_skill_rejects_missing_unsafe_and_large_files(self):
        for files in [{'SKILL.md':'[rules](references/missing.md)'}, {'../SKILL.md':'x'}, {'SKILL.md':'x'*270000}]:
            with self.subTest(files=list(files)):
                with self.assertRaises(ValueError):load_director_skill({'entrypoint':'SKILL.md','files':files})

    def test_plan_preserves_dialogue_and_source(self):
        result=validate_plan(plan(),STORY)
        self.assertEqual(result['shots'][0]['dialogue'],'Alex [English]: Coffee?')
        for mutate in [lambda p:p['shots'][0].update(duration_s=float('nan')),
                       lambda p:p['shots'][0].update(source_excerpt='Invented scene'),
                       lambda p:p['shots'][0]['dialogue_lines'][0].update(text='Tea?'),
                       lambda p:p['shots'][0]['continuity'].update(mode='continue',source_shot_key='a')]:
            bad=plan();mutate(bad)
            with self.assertRaises(ValueError):validate_plan(bad,STORY)
        duplicate=plan();duplicate['shots'].append(copy.deepcopy(duplicate['shots'][0]))
        with self.assertRaises(ValueError):validate_plan(duplicate,STORY)

    def test_plan_cannot_silently_drop_the_end_or_dialogue(self):
        with self.assertRaisesRegex(ValueError,'complete script'):
            validate_plan(plan(),STORY+' Later the lights go out.')
        bad=plan();bad['shots'][0]['dialogue_lines']=[]
        with self.assertRaisesRegex(ValueError,'dialogue'):
            validate_plan(bad,STORY)

    def test_repeated_source_beats_and_screenplay_dialogue_are_not_dropped(self):
        bad=plan();bad['shots'][0].update(source_excerpt='Alex opens the door.',dialogue_lines=[])
        with self.assertRaisesRegex(ValueError,'complete script'):
            validate_plan(bad,'Alex opens the door.\nMia opens the door.')
        script='INT. ROOM\nMIA\nCoffee?\n\nTAO\nNo thanks.'
        bad['shots'][0]['source_excerpt']=script
        with self.assertRaisesRegex(ValueError,'dialogue'):
            validate_plan(bad,script)

    def test_explicit_speaker_and_language_are_preserved(self):
        bad=plan();bad['shots'][0]['dialogue_lines'][0]['speaker']='Jordan'
        with self.assertRaisesRegex(ValueError,'speaker'):
            validate_plan(bad,STORY)
        script='Alex [English]: Coffee?'
        bad=plan();bad['shots'][0]['source_excerpt']=script;bad['shots'][0]['dialogue_lines'][0]['language']='French'
        with self.assertRaisesRegex(ValueError,'language'):
            validate_plan(bad,script)

    def test_service_selection_sends_inventory_but_not_credentials_or_images(self):
        from test_contract import workspace
        class Client:
            def complete_json(self,stage,system,payload,**kwargs):
                self.payload=payload
                return {'value':kwargs['validate']({'selections':[{'asset_id':'actor','reason':'Identity'}],'missing':[]}),
                        'timing':{'stage':stage,'total_ms':1}}
        data=workspace();data['llm_config']={'api_key_env':'SECRET_NAME'}
        client=Client();result=PlanningService(client).select(data)
        self.assertEqual(result['refs'][0]['asset_id'],'actor')
        self.assertNotIn('llm_config',client.payload);self.assertNotIn('image',client.payload['assets'][0])

    def test_selection_rejects_invented_duplicate_and_undescribed_assets(self):
        assets=[{'id':'alex','name':'Alex','image':'alex.png','description':'Alex identity sheet'},
                {'id':'room','name':'Room','image':'room.png','description':''}]
        selected={'selections':[{'asset_id':'alex','reason':'Visible performer identity'}],'missing':['Coffee cup']}
        self.assertEqual(validate_selection(selected,assets)['refs'][0]['asset_id'],'alex')
        for asset_id in ['unknown','room']:
            bad=copy.deepcopy(selected);bad['selections'][0]['asset_id']=asset_id
            with self.assertRaises(ValueError):validate_selection(bad,assets)
        bad=copy.deepcopy(selected);bad['selections']*=2
        with self.assertRaises(ValueError):validate_selection(bad,assets)

    def test_services_are_scoped_and_pass_rules_before_story(self):
        class Client:
            def complete_json(self,stage,system,payload,**kwargs):
                self.stage,self.system,self.payload,self.kwargs=stage,system,payload,kwargs
                return {'value':kwargs['validate'](plan()),'timing':{'stage':stage,'total_ms':1}}
        client=Client();service=PlanningService(client)
        result=service.plan({'script':STORY,'director_skill':{'files':{'SKILL.md':'DIRECTOR RULE'}}})
        self.assertEqual(client.stage,'script_plan');self.assertIn('DIRECTOR RULE',client.system)
        self.assertNotIn(STORY,client.system);self.assertEqual(client.payload['script'],STORY)
        self.assertTrue(result['shots']);self.assertEqual(len(result['rule_manifest']['version']),64)

if __name__=='__main__':unittest.main()
