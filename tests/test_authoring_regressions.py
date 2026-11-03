import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contract import make_shot
from llm_runtime import AuthoringService
from test_contract import workspace
VIEW='Camera stays at the unseen observer\'s eyes, never behind the observer; no observer head, hair, neck, shoulders, back, torso, shadow or reflection appears.'

LINE="That's me. Unless you're looking for Mia. She's at the flower shop."

class CandidateClient:
    def __init__(self,candidate):self.candidate=candidate;self.payload=None
    def complete_json(self,stage,instructions,payload,validate,**kwargs):
        self.payload=payload
        return {'value':validate(copy.deepcopy(self.candidate)),'timing':{'stage':stage,'model':'fixture','llm_ms':0,'total_ms':0,'calls':[]}}

def data():
    ws=workspace();ws['shots'][0]['brief']='Strict first-person POV from an unseen customer at the bakery counter. The baker says: "'+LINE+'"'
    return ws

def sections(line=LINE):
    value={key:'None' for key in ['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']}
    value['subject_definitions']='<Picture 1> counter; <Picture 2> baker'
    value['detailed_description']=VIEW+' Customer remains outside the counter. (S2) <d>[English] '+line+'</d>'
    return value

class AuthoringRegressions(unittest.TestCase):
    def timed_workspace(self):
        ws=data();ws['shots'][0]['duration_s']=10
        ws['shots'][0]['continuity']={'mode':'external_workflow','delivery_timing':{'prefix_trim_frames':22,'fps':24,'speech_lead_in_s':.35,'speech_tail_hold_s':.6}}
        return ws

    def test_writer_receives_actual_retained_speech_window(self):
        candidate=sections();candidate['detailed_description']=VIEW+'\n[1.3–8.5s] Mia: <d>[English] '+LINE+'</d>'
        client=CandidateClient(candidate);AuthoringService(client).write_prompt(self.timed_workspace())
        timing=client.payload['delivery_timing']
        self.assertAlmostEqual(timing['prefix_trim_s'],22/24)
        self.assertAlmostEqual(timing['sampling_end_s'],243/24)
        self.assertGreaterEqual(timing['speech_start_s'],22/24+.35)
        self.assertAlmostEqual(timing['speech_start_s'],22/24+.35,delta=.001)
        self.assertAlmostEqual(timing['speech_end_s'],243/24-.6)

    def test_dialogue_cannot_start_in_trimmed_context_or_end_in_tail_guard(self):
        for interval in ['0–5s','1.3–10s']:
            candidate=sections();candidate['detailed_description']='['+interval+'] Mia: <d>[English] '+LINE+'</d>'
            with self.subTest(interval=interval),self.assertRaisesRegex(ValueError,'speech window'):
                AuthoringService(CandidateClient(candidate)).write_prompt(self.timed_workspace())

    def test_context_timing_requires_explicit_dialogue_interval(self):
        with self.assertRaisesRegex(ValueError,'speech window'):
            AuthoringService(CandidateClient(sections())).write_prompt(self.timed_workspace())

    def test_strict_unseen_pov_direction_must_reach_generated_prompt(self):
        candidate=sections();candidate['detailed_description']=candidate['detailed_description'].replace(VIEW,'')
        with self.assertRaisesRegex(ValueError,'observer direction'):
            AuthoringService(CandidateClient(candidate)).write_prompt(data())

    def test_refined_unseen_eye_level_description_keeps_pov_constraints(self):
        ws=data();ws['shots'][0]['brief']='Camera positioned at the unseen customer’s eye level. Mia says: "'+LINE+'"'
        candidate=sections();candidate['detailed_description']=candidate['detailed_description'].replace(VIEW,'')
        with self.assertRaisesRegex(ValueError,'observer direction'):
            AuthoringService(CandidateClient(candidate)).write_prompt(ws)

    def test_invalid_context_budget_is_rejected_before_model_request(self):
        for value in [-1,243,True]:
            ws=self.timed_workspace();ws['shots'][0]['continuity']['delivery_timing']['prefix_trim_frames']=value
            client=CandidateClient(sections())
            with self.subTest(value=value),self.assertRaises(ValueError):AuthoringService(client).write_prompt(ws)
            self.assertIsNone(client.payload)

    def test_silent_continuation_does_not_need_spoken_interval(self):
        ws=self.timed_workspace();ws['shots'][0]['brief']='Silent first-person movement toward the blue door.'
        candidate=sections();candidate['detailed_description']='The empty foreground moves toward the blue door. No speech.'
        self.assertIn('prompt_sections',AuthoringService(CandidateClient(candidate)).write_prompt(ws))

    def test_refine_extracts_exact_brief_dialogue_and_returns_it_without_mutation(self):
        ws=data();before=copy.deepcopy(ws);client=CandidateClient({'description':ws['shots'][0]['brief']})
        result=AuthoringService(client).refine_description(ws)
        self.assertIn(LINE,result['dialogue']);self.assertEqual(ws,before)

    def test_write_accepts_literal_speech_in_brief_without_separate_dialogue(self):
        client=CandidateClient(sections());result=AuthoringService(client).write_prompt(data())
        self.assertIn(LINE,result['prompt_sections']['detailed_description']);self.assertIn(LINE,client.payload['dialogue'])

    def test_reference_manifest_is_ordered_and_honest_about_saved_evidence(self):
        client=CandidateClient(sections());AuthoringService(client).write_prompt(data())
        self.assertFalse(client.payload['reference_evidence']['image_pixels_in_this_request'])
        self.assertEqual([r['picture_tag'] for r in client.payload['references']],['<Picture 1>','<Picture 2>'])
        self.assertTrue(all(r['evidence_source']=='saved_asset_description' and r['asset_id'] for r in client.payload['references']))

    def test_bare_language_word_is_not_accepted_as_authored_speech(self):
        with self.assertRaisesRegex(ValueError,'Expected spoken text:.*square brackets'):
            AuthoringService(CandidateClient(sections('English '+LINE))).write_prompt(data())

    def test_refine_repair_identifies_speaker_name_inside_spoken_block(self):
        with self.assertRaisesRegex(ValueError,'Expected spoken text:.*outside'):
            AuthoringService(CandidateClient({'description':'Mia speaks: <d>Mia: '+LINE+'</d>'})).refine_description(data())

    def test_curly_speech_quote_and_contractions_are_preserved(self):
        ws=data();ws['shots'][0]['brief']='The baker speaks: “'+LINE.replace("'",'’')+'”'
        result=AuthoringService(CandidateClient(sections())).write_prompt(ws)
        self.assertIn(LINE,result['prompt_sections']['detailed_description'])

    def test_sign_text_is_not_inferred_as_spoken_dialogue(self):
        ws=workspace();ws['shots'][0]['brief']='The bakery sign reads "Mia". No dialogue.'
        with self.assertRaisesRegex(ValueError,'dialogue'):
            AuthoringService(CandidateClient(sections('Mia'))).write_prompt(ws)

    def test_explicit_dialogue_does_not_authorize_extra_speech(self):
        ws=data();ws['shots'][0]['dialogue']='Mia [English]: '+LINE
        with self.assertRaisesRegex(ValueError,'dialogue|speech'):
            AuthoringService(CandidateClient(sections(LINE+' Have a nice day!'))).write_prompt(ws)

    def test_quoted_dialogue_block_is_not_mistaken_for_extra_words(self):
        result=AuthoringService(CandidateClient(sections('"'+LINE+'"'))).write_prompt(data())
        self.assertIn(LINE,result['prompt_sections']['detailed_description'])

    def test_writer_cannot_add_background_customer_chatter(self):
        value=sections();value['overall_soundscape']='Oven hum, occasional murmur of customers in the background.'
        with self.assertRaisesRegex(ValueError,'background|speech'):
            AuthoringService(CandidateClient(value)).write_prompt(data())

    def test_negative_background_instruction_is_not_treated_as_added_chatter(self):
        value=sections();value['overall_soundscape']='Oven hum. No background chatter.'
        self.assertEqual(AuthoringService(CandidateClient(value)).write_prompt(data())['prompt_sections'],value)

    def test_printed_line_is_not_inferred_as_dialogue(self):
        ws=workspace();ws['shots'][0]['brief']='A printed line: "Mia" appears on a photo. No dialogue.'
        with self.assertRaisesRegex(ValueError,'dialogue'):
            AuthoringService(CandidateClient(sections('Mia'))).write_prompt(ws)

    def test_sign_says_is_not_authorization_for_speech(self):
        ws=workspace();ws['shots'][0]['brief']='The sign says: "Closed". No dialogue.'
        with self.assertRaisesRegex(ValueError,'dialogue'):
            AuthoringService(CandidateClient(sections('Closed'))).write_prompt(ws)

    def test_refine_rejects_new_or_expanded_speech(self):
        ws=data()
        for extra in [' Then the customer says "Goodbye".', '']:
            text=ws['shots'][0]['brief']+extra if extra else ws['shots'][0]['brief'].replace(LINE,LINE+' Have a nice day!')
            with self.subTest(text=text),self.assertRaisesRegex(ValueError,'dialogue|speech'):
                AuthoringService(CandidateClient({'description':text})).refine_description(ws)

    def test_write_rejects_quoted_speech_outside_dialogue_blocks(self):
        value=sections();value['detailed_description']+=' Then the customer says "Goodbye".'
        with self.assertRaisesRegex(ValueError,'dialogue|speech'):
            AuthoringService(CandidateClient(value)).write_prompt(data())

    def test_refine_accepts_speaks_directly_to_camera_cue(self):
        ws=data();text='The baker Mia speaks directly to the camera: “'+LINE.replace("'",'’')+'”'
        self.assertEqual(AuthoringService(CandidateClient({'description':text})).refine_description(ws)['description'],text)

    def test_speaker_holding_printed_prop_can_still_speak(self):
        ws=data();ws['shots'][0]['brief']='The baker holds a menu and says: "'+LINE+'"'
        self.assertIn(LINE,AuthoringService(CandidateClient(sections())).write_prompt(ws)['prompt_sections']['detailed_description'])

    def test_refine_accepts_existing_explicit_speaker_language_cue(self):
        ws=data();ws['shots'][0]['dialogue']='Mia [English]: '+LINE
        text='Mia [English]: '+LINE
        result=AuthoringService(CandidateClient({'description':text})).refine_description(ws)
        self.assertEqual(result['dialogue'],ws['shots'][0]['dialogue'])

    def test_refine_cannot_drop_or_paraphrase_the_authored_line(self):
        with self.assertRaisesRegex(ValueError,'dialogue'):
            AuthoringService(CandidateClient({'description':'The baker sends the customer to the florist.'})).refine_description(data())

    def test_refine_cannot_move_customer_behind_counter(self):
        ws=data();candidate={'description':ws['shots'][0]['brief']+' The customer is standing behind the bakery counter.'}
        with self.assertRaisesRegex(ValueError,'counter|staging'):
            AuthoringService(CandidateClient(candidate)).refine_description(ws)

    def test_baker_behind_counter_is_not_misidentified_as_customer(self):
        ws=data();candidate={'description':ws['shots'][0]['brief']+' The customer faces the baker behind the counter.'}
        result=AuthoringService(CandidateClient(candidate)).refine_description(ws)
        self.assertEqual(result['description'],candidate['description'])

    def test_negative_counter_instruction_is_not_treated_as_a_move(self):
        ws=data();candidate={'description':ws['shots'][0]['brief']+' No customer is standing behind the counter.'}
        self.assertEqual(AuthoringService(CandidateClient(candidate)).refine_description(ws)['description'],candidate['description'])

    def test_snapshot_does_not_mislabel_sampling_duration_as_delivered_duration(self):
        ws=workspace();ws['shots'][0]['duration_s']=10;shot=make_shot(json.dumps(ws))
        self.assertEqual(shot['length'],243)
        self.assertEqual(shot['sampling_duration_s'],10.125)
        self.assertIsNone(shot['actual_duration_s'])
        self.assertEqual(shot['duration_semantics'],'sampling_input_before_workflow_trim')

if __name__=='__main__':unittest.main()
