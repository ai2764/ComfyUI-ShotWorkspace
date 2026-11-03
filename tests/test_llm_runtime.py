import json
import sys
import tempfile
import threading
import unittest
import shutil
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from llm_runtime import LLMClient, AuthoringService, parse_object
from test_contract import workspace
from authoring_skill import load_rule_bundle,ROOT


class Handler(BaseHTTPRequestHandler):
    responses = []
    requests = []
    on_request = None

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.requests.append(body)
        if type(self).on_request:type(self).on_request(len(self.requests))
        candidate = self.responses.pop(0)
        status = candidate.pop('_http_status', 200)
        raw = json.dumps(candidate).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


def response(content, finish='stop'):
    return {'choices': [{'message': {'content': content}, 'finish_reason': finish}],
            'usage': {'prompt_tokens': 20, 'completion_tokens': 10}}


class RuntimeTests(unittest.TestCase):
    def test_final_channel_framing_is_removed_without_accepting_arbitrary_prose(self):
        self.assertEqual(parse_object('<|channel|>final <|constrain|>JSON<|message|>{"description":"Gentle action."}'), {'description':'Gentle action.'})
        with self.assertRaises(ValueError):
            parse_object('Here is a claim, not a JSON response: {"description":"Do not silently extract this."}')

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Handler.requests = []
        Handler.responses = []
        Handler.on_request=None
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'calls.jsonl'
        self.config = {'base_url': f'http://127.0.0.1:{self.server.server_port}/v1',
                       'text_model': 'example-model', 'vision_model': 'example-model', 'api_key_env': '', 'timeout_s': 5}
        self.client = LLMClient(self.config, self.path)

    def test_vision_contains_pixels_and_every_attempt_has_timing(self):
        Handler.responses = [response('{"description":"A blue square."}')]
        result = AuthoringService(self.client).describe_asset({'id': 'asset', 'name': 'Panel'}, 'data:image/jpeg;base64,AAAA')
        self.assertEqual(result['description'], 'A blue square.')
        self.assertIn('image_url', json.dumps(Handler.requests[0]))
        calls = [json.loads(line) for line in self.path.read_text().splitlines()]
        self.assertEqual(calls[0]['stage'], 'asset_analysis')
        self.assertTrue(calls[0]['success'])
        self.assertGreater(calls[0]['elapsed_ms'], 0)
        self.assertEqual(calls[0]['model'], 'example-model')
        self.assertEqual(calls[0]['rule_bundle']['stage'],'asset_analysis')
        self.assertEqual(calls[0]['rule_bundle'],result['timing']['rule_bundle'])
        bundle_file=self.path.parent/'rule-bundles'/(calls[0]['rule_bundle']['version']+'.json')
        self.assertEqual(json.loads(bundle_file.read_text())['system'],Handler.requests[0]['messages'][0]['content'])

    def test_connection_probes_both_text_and_image_without_a_workspace(self):
        Handler.responses = [response('{"ok":true}'), response('{"colour":"blue"}')]
        result = AuthoringService(self.client).test_connection('data:image/png;base64,AAAA')
        self.assertTrue(result['success'])
        self.assertEqual(result['text']['model'], 'example-model')
        self.assertEqual(result['vision']['model'], 'example-model')
        self.assertNotIn('image_url', json.dumps(Handler.requests[0]))
        self.assertIn('image_url', json.dumps(Handler.requests[1]))
        self.assertEqual(len(Handler.requests), 2)

    def test_rule_snapshot_stays_fixed_through_repair_then_refreshes_next_operation(self):
        root=Path(self.temp.name)/'rules';shutil.copytree(ROOT,root)
        first=load_rule_bundle('description_refine',root)
        target=root/'stages/refine.md'
        Handler.on_request=lambda count:target.write_text(target.read_text()+'\nNEW RULE AFTER FIRST REQUEST',encoding='utf-8') if count==1 else None
        Handler.responses=[response('{"description":""}'),response('{"description":"A person enters the room."}')]
        with patch('llm_runtime.load_rule_bundle',side_effect=lambda stage:load_rule_bundle(stage,root)):
            result=AuthoringService(self.client).refine_description(workspace())
        versions=[c['rule_bundle']['version'] for c in result['timing']['calls']]
        self.assertEqual(versions,[first.version,first.version])
        self.assertNotIn('NEW RULE AFTER',json.dumps(Handler.requests))
        self.assertNotEqual(load_rule_bundle('description_refine',root).version,first.version)

    def test_failed_authoring_also_retains_rule_identity_and_saved_draft(self):
        data=workspace();before=json.dumps(data)
        Handler.responses=[response('{"description":""}'),response('{"description":""}')]
        with self.assertRaisesRegex(ValueError,'Missing description'):AuthoringService(self.client).refine_description(data)
        records=[json.loads(line) for line in self.path.read_text().splitlines()]
        self.assertTrue(all(c['rule_bundle']['stage']=='description_refine' for c in records))
        self.assertEqual(json.dumps(data),before)

    def test_connection_rejects_a_vision_probe_that_did_not_read_the_image(self):
        Handler.responses = [response('{"ok":true}'), response('{"colour":"red"}'), response('{"colour":"red"}')]
        with self.assertRaisesRegex(ValueError, 'blue'):
            AuthoringService(self.client).test_connection('data:image/png;base64,AAAA')

    def test_failed_candidate_repair_is_bounded_and_timed_separately(self):
        Handler.responses = [response('not json'), response('{"description":"Fixed."}')]
        result = self.client.complete_json('description_refine', 'Return JSON', {'brief': 'Test'},
            validate=lambda v: v if v.get('description') else (_ for _ in ()).throw(ValueError('missing description')))
        self.assertEqual(result['value']['description'], 'Fixed.')
        self.assertEqual(len(result['timing']['calls']), 2)
        self.assertFalse(result['timing']['calls'][0]['success'])
        self.assertTrue(result['timing']['calls'][1]['success'])
        self.assertEqual(len(Handler.requests), 2)

    def test_truncated_result_is_not_applied_or_repaired(self):
        Handler.responses = [response('{"description":"partial"}', 'length')]
        with self.assertRaisesRegex(ValueError, 'truncated'):
            self.client.complete_json('description_refine', 'JSON', {}, validate=lambda v: v)
        self.assertEqual(len(Handler.requests), 1)
        self.assertFalse(json.loads(self.path.read_text())['success'])

    def test_provider_format_rejection_retries_as_text_and_records_both_calls(self):
        Handler.responses = [
            {'_http_status': 400, 'error': "'response_format.type' must be 'json_schema' or 'text'"},
            response('{"description":"A gentle chin scratch."}')]
        result = self.client.complete_json('description_refine', 'Return JSON', {}, validate=lambda v: v)
        self.assertEqual(result['value']['description'], 'A gentle chin scratch.')
        self.assertEqual([r['response_format']['type'] for r in Handler.requests], ['json_object', 'text'])
        self.assertEqual([c['success'] for c in result['timing']['calls']], [False, True])
        self.assertIn('response_format.type', result['timing']['calls'][0]['error'])

    def test_provider_error_body_is_actionable_and_not_retried_without_format_rejection(self):
        Handler.responses = [{'_http_status': 400, 'error': {'message': 'Selected model is unavailable.'}}]
        with self.assertRaisesRegex(ValueError, 'HTTP 400: Selected model is unavailable'):
            self.client.complete_json('description_refine', 'Return JSON', {}, validate=lambda v: v)
        self.assertEqual(len(Handler.requests), 1)

    def test_format_negotiation_preserves_the_candidate_repair_budget(self):
        data = workspace()
        sections = {k: 'None' for k in ['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']}
        sections['subject_definitions'] = '<Picture 1> room; <Picture 2> person'
        Handler.responses = [
            {'_http_status':400,'error':"'response_format.type' must be 'json_schema' or 'text'"},
            response(json.dumps(dict(sections,non_diegetic_music=None))),
            response(json.dumps(sections))]
        result = AuthoringService(self.client).write_prompt(data)
        self.assertEqual(result['prompt_sections']['non_diegetic_music'], 'None')
        self.assertEqual(len(result['timing']['calls']), 3)
        self.assertIn('repair',json.loads(Handler.requests[2]['messages'][1]['content']))

    def test_refine_only_gets_selected_text_and_bounded_previous_description(self):
        data = workspace()
        first = dict(data['shots'][0], id='s0', brief='x' * 2200)
        data['shots'].insert(0, first)
        data['assets'].append({'id': 'unused', 'description': 'SECRET_UNUSED_TEXT'})
        Handler.responses = [response('{"description":"Walk into the room slowly."}')]
        result = AuthoringService(self.client).refine_description(data, 'Make it slower')
        sent = json.dumps(Handler.requests[0])
        self.assertNotIn('image_url', sent)
        self.assertNotIn('SECRET_UNUSED_TEXT', sent)
        payload = json.loads(Handler.requests[0]['messages'][1]['content'])
        self.assertEqual(len(payload['previous_shot_description']['description']), 2000)
        self.assertTrue(payload['previous_shot_description']['truncated'])
        self.assertEqual(result['description'], 'Walk into the room slowly.')

    def test_writer_repairs_unselected_reference_without_mutating_saved_prompt(self):
        data = workspace()
        original = json.dumps(data)
        sections = {k: 'None' for k in ['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']}
        bad = dict(sections, subject_definitions='<Picture 99>')
        good = dict(sections, subject_definitions='<Picture 1> room; <Picture 2> person')
        Handler.responses = [response(json.dumps(bad)), response(json.dumps(good))]
        result = AuthoringService(self.client).write_prompt(data)
        self.assertEqual(result['prompt_sections'], good)
        self.assertEqual(len(result['timing']['calls']), 2)
        self.assertEqual(json.dumps(data), original)
        self.assertIn('Validation repair',Handler.requests[1]['messages'][0]['content'])
        repair_messages=Handler.requests[1]['messages']
        self.assertEqual([m['role'] for m in repair_messages],['system','user','assistant','user'])
        self.assertEqual(json.loads(repair_messages[2]['content']),bad)
        self.assertIn(json.loads(repair_messages[1]['content'])['repair']['reason'],repair_messages[3]['content'])

    def test_writer_receives_literal_tags_and_normalizes_explicit_bare_mentions(self):
        data = workspace()
        keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
        sections={k:'None' for k in keys}
        sections['subject_definitions']='Picture 1 defines the room; Picture 2 defines the person.'
        Handler.responses=[response(json.dumps(sections))]
        result=AuthoringService(self.client).write_prompt(data)
        sent=json.loads(Handler.requests[0]['messages'][1]['content'])
        self.assertEqual(sent['required_picture_tags'],['<Picture 1>','<Picture 2>'])
        self.assertIn('<Picture 1>',result['prompt_sections']['subject_definitions'])


if __name__ == '__main__':
    unittest.main()
