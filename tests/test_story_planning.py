import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planning import PlanningService


class Client:
    def __init__(self, value): self.value=value; self.calls=[]
    def complete_json(self, stage, system, payload, **kwargs):
        self.calls.append((stage,system,payload,kwargs))
        return {'value':kwargs['validate'](copy.deepcopy(self.value)), 'timing':{'total_ms':12,'stage':stage}}


def candidate():
    return {'title':'The last slice','shots':[
        {'shot_key':'a','title':'Offer','brief':'Alex looks at Jordan over the bread.', 'duration_s':8,
         'dialogue_lines':[{'speaker':'Alex','language':'English','text':'Want to share?'}],
         'continuity':{'mode':'off'},'dramatic_beat':{'start_state':'Jordan is alone.','change':'Alex offers company.','end_state':'Jordan listens.','cut_reason':'Show the invitation and its listener.'}},
        {'shot_key':'b','title':'Stay','brief':'They settle beside the shared plate.','duration_s':8,
         'dialogue_lines':[{'speaker':'Jordan','language':'English','text':'Please stay.'}],
         'continuity':{'mode':'off'},'dramatic_beat':{'start_state':'An offer is open.','change':'Jordan accepts.','end_state':'They stay together.','cut_reason':'Resolve the shared choice.'}}]}


class StoryPlanningTests(unittest.TestCase):
    def test_plain_story_directly_yields_shots_and_original_dialogue_in_one_call(self):
        client=Client(candidate())
        result=PlanningService(client).story_plan({'story':'Two people share bread. One is lonely; the other stays.','target_duration_s':30})
        self.assertEqual(len(client.calls),1)
        self.assertEqual(client.calls[0][0],'story_plan')
        self.assertEqual(len(result['shots']),2)
        self.assertIn('Want to share?',result['shots'][0]['dialogue'])
        self.assertEqual(result['source_kind'],'model_authored_from_story')
        self.assertNotIn('script',result)

    def test_duration_budget_and_supplied_exact_dialogue_remain_constraints(self):
        value=candidate();value['shots'][0]['duration_s']=30
        with self.assertRaisesRegex(ValueError,'duration'):
            PlanningService(Client(value)).story_plan({'story':'They share bread.','target_duration_s':20})
        with self.assertRaisesRegex(ValueError,'dialogue'):
            PlanningService(Client(candidate())).story_plan({'story':'Alex [English]: Keep these exact words.'})

    def test_no_dialogue_required_and_long_unformatted_notes_are_accepted(self):
        value=candidate()
        for shot in value['shots']:shot['dialogue_lines']=[]
        client=Client(value)
        result=PlanningService(client).story_plan({'story':'rough notes, not a screenplay; '*200})
        self.assertEqual(result['shots'][0]['dialogue'],'')
        self.assertGreater(len(client.calls[0][2]['story']),4000)

    def test_invalid_input_fails_before_model_call(self):
        for body in [{'story':''},{'story':'x'*40001},{'story':'Hi','target_duration_s':True}]:
            client=Client(candidate())
            with self.assertRaises(ValueError):PlanningService(client).story_plan(body)
            self.assertEqual(client.calls,[])
