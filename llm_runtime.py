"""OpenAI-compatible authoring with bounded repair and per-call timing receipts."""
import copy
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from .contract import SECTION_KEYS, make_shot, llm_config
    from .authoring_rules import authored_dialogue, validate_spoken_words, validate_refinement, delivery_window, validate_speech_window
    from .authoring_skill import load_rule_bundle
except ImportError:
    from contract import SECTION_KEYS, make_shot, llm_config
    from authoring_rules import authored_dialogue, validate_spoken_words, validate_refinement, delivery_window, validate_speech_window
    from authoring_skill import load_rule_bundle

_ledger_lock = threading.Lock()


def parse_object(text):
    text = text.strip()
    text = re.sub(r'^<\|channel\|>final\s*(?:<\|constrain\|>JSON)?<\|message\|>', '', text).strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text).strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object.')
    return value


class LLMClient:
    def __init__(self, config, timing_path):
        self.config = llm_config(config['base_url'], config.get('text_model', ''), config.get('vision_model', ''),
                                 config.get('api_key_env', ''), config.get('timeout_s', 180))
        self.timing_path = Path(timing_path)

    def _record(self, record):
        self.timing_path.parent.mkdir(parents=True, exist_ok=True)
        with _ledger_lock, self.timing_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')

    def complete_json(self, stage, system, payload, *, validate, image_url=None, shot_id=None, asset_id=None, max_tokens=3072, rule_manifest=None):
        model = self.config['vision_model' if image_url else 'text_model']
        if not model.strip():
            raise ValueError('Set a vision model for image analysis and a text model for writing.')
        rule_manifest=copy.deepcopy(rule_manifest)
        if rule_manifest is not None:
            version=rule_manifest.get('version','')
            if not isinstance(version,str) or not re.fullmatch('[0-9a-f]{64}',version):raise ValueError('Invalid rule-bundle version.')
            bundles=self.timing_path.parent/'rule-bundles';bundles.mkdir(parents=True,exist_ok=True)
            with _ledger_lock:
                try:
                    with (bundles/(version+'.json')).open('x',encoding='utf-8') as stream:
                        json.dump({'manifest':rule_manifest,'system':system},stream,ensure_ascii=False,indent=2)
                except FileExistsError:pass
        stage_started = time.perf_counter()
        operation_id = uuid.uuid4().hex
        calls = []
        candidate, reason = None, None
        response_type = 'json_object'
        for attempt in range(1, 4):
            facts = copy.deepcopy(payload)
            if reason:
                facts['repair'] = {'reason': reason,
                                   'instruction': 'Return a complete repaired JSON object. Preserve the supplied references and authored intent.'}
            content = json.dumps(facts, ensure_ascii=False)
            if image_url:
                content = [{'type': 'text', 'text': content}, {'type': 'image_url', 'image_url': {'url': image_url}}]
            system_message=system
            if reason:
                system_message+='\nValidation repair: '+reason+'\nCorrect this error in the complete JSON response. Keep the authored facts; do not repeat the invalid candidate unchanged.'
            messages=[{'role': 'system', 'content': system_message}, {'role': 'user', 'content': content}]
            if reason and candidate:
                try:
                    previous=json.dumps(parse_object(candidate),ensure_ascii=False)
                except (ValueError,TypeError):
                    previous=candidate
                messages.extend([{'role':'assistant','content':previous},
                    {'role':'user','content':'The previous JSON failed validation: '+reason+'\nReturn a complete corrected JSON object. Follow the original authored facts and the system instructions.'}])
            body = {'model': model, 'messages': messages,
                    'max_tokens': max_tokens, 'temperature': 0.15, 'stream': False,
                    'response_format': {'type': response_type}}
            if 'qwen' in model.lower():
                body['chat_template_kwargs'] = {'enable_thinking': False}
            headers = {'Content-Type': 'application/json'}
            env_name = self.config.get('api_key_env')
            if env_name:
                key = os.environ.get(env_name)
                if not key:
                    raise ValueError(f'API key environment variable {env_name} is not set.')
                headers['Authorization'] = 'Bearer ' + key
            request = urllib.request.Request(self.config['base_url'] + '/chat/completions',
                data=json.dumps(body, ensure_ascii=False).encode(), headers=headers, method='POST')
            started = time.perf_counter()
            record = {'id': uuid.uuid4().hex, 'operation_id': operation_id, 'stage': stage, 'attempt': attempt,
                      'model': model, 'base_url': self.config['base_url'], 'shot_id': shot_id, 'asset_id': asset_id,
                      'started_at': datetime.now(timezone.utc).isoformat(), 'success': False}
            if rule_manifest is not None:record['rule_bundle']=copy.deepcopy(rule_manifest)
            response = None
            try:
                with urllib.request.urlopen(request, timeout=self.config['timeout_s']) as stream:
                    response = json.load(stream)
                record['elapsed_ms'] = round((time.perf_counter() - started) * 1000, 2)
                record['usage'] = response.get('usage', {})
                choices = response.get('choices') or []
                if not choices:
                    raise ValueError('Model returned no choices.')
                if choices[0].get('finish_reason') in {'length', 'max_tokens'}:
                    raise ValueError('Model response was truncated. No partial result was applied.')
                candidate = choices[0].get('message', {}).get('content') or ''
                responses = self.timing_path.parent / 'responses'
                responses.mkdir(exist_ok=True)
                (responses / f'{operation_id}-{attempt}.json').write_text(json.dumps({
                    'stage': stage, 'model': model, 'content': candidate, 'usage': response.get('usage', {}),
                    **({'rule_bundle':rule_manifest} if rule_manifest is not None else {})},
                    ensure_ascii=False, indent=2), encoding='utf-8')
                value = validate(parse_object(candidate))
                record['success'] = True
                calls.append(record)
                self._record(record)
                return {'value': value, 'timing': {'stage': stage, 'model': model, 'calls': calls,
                        'llm_ms': round(sum(c['elapsed_ms'] for c in calls), 2),
                        'total_ms': round((time.perf_counter() - stage_started) * 1000, 2),
                        **({'rule_bundle':copy.deepcopy(rule_manifest)} if rule_manifest is not None else {})}}
            except Exception as exc:
                record.setdefault('elapsed_ms', round((time.perf_counter() - started) * 1000, 2))
                if isinstance(exc, urllib.error.HTTPError):
                    detail = exc.read(4096).decode(errors='replace')
                    exc.close()
                    try:
                        detail = json.loads(detail).get('error', detail)
                    except (ValueError, AttributeError):
                        pass
                    if isinstance(detail, dict):
                        detail = detail.get('message', str(detail))
                    detail = ' '.join(str(detail).split())[:400]
                    record['error'] = f'HTTP {exc.code}: {detail}'
                else:
                    record['error'] = str(exc)[:500]
                calls.append(record)
                self._record(record)
                if (isinstance(exc, urllib.error.HTTPError) and exc.code == 400 and attempt == 1
                        and 'response_format' in detail and ('text' in detail or 'not support' in detail.lower())):
                    response_type = 'text'
                    continue
                if (isinstance(exc, (urllib.error.URLError, TimeoutError)) or 'truncated' in str(exc).lower()
                        or attempt >= (3 if response_type == 'text' else 2)):
                    raise ValueError(f'{stage} failed: {record["error"].rstrip(".")}. Existing draft/prompt was kept.') from exc
                reason = str(exc)


class AuthoringService:
    def __init__(self, client):
        self.client = client

    def test_connection(self, image_url):
        def validate_text(value):
            if value.get('ok') is not True:
                raise ValueError('Text probe must return {"ok":true}.')
            return value
        def validate_vision(value):
            if str(value.get('colour', '')).strip().lower() != 'blue':
                raise ValueError('Vision probe must identify the blue test image.')
            return value
        text = self.client.complete_json('connection_test_text',
            'Connection check. Return exactly the JSON object {"ok":true}.', {},
            validate=validate_text, max_tokens=256)
        vision = self.client.complete_json('connection_test_vision',
            'Look at the supplied solid-colour image. Return JSON with one field "colour", '
            'the dominant colour in English. Do not infer it from text.', {},
            validate=validate_vision, image_url=image_url, max_tokens=256)
        return {'success': True,
                'text': {'model': self.client.config['text_model'], 'llm_ms': text['timing']['llm_ms']},
                'vision': {'model': self.client.config['vision_model'], 'llm_ms': vision['timing']['llm_ms']}}

    def describe_asset(self, asset, image_url):
        bundle=load_rule_bundle('asset_analysis')
        instructions=bundle.text
        def validate(value):
            text = value.get('description')
            if not isinstance(text, str) or not text.strip():
                raise ValueError('Missing nonempty description.')
            return {'description': text.strip()}
        result = self.client.complete_json('asset_analysis', instructions,
            {'name': asset.get('name', ''), 'existing_description': asset.get('description', '')},
            validate=validate, image_url=image_url, asset_id=asset.get('id'), max_tokens=2048,rule_manifest=bundle.manifest())
        return {**result['value'], 'timing': result['timing']}

    def _context(self, workspace):
        shot = make_shot(json.dumps(workspace, ensure_ascii=False))
        if any(not ref['description'].strip() for ref in shot['references']):
            raise ValueError('Analyse or describe every selected image before writing.')
        position = next(i for i, s in enumerate(workspace['shots']) if s['id'] == shot['shot_id'])
        previous = workspace['shots'][position - 1] if position else None
        previous_text = str(previous.get('brief', '')) if previous else ''
        source = workspace['shots'][position]
        payload = {'shot': {k: shot[k] for k in ('shot_id', 'title', 'brief', 'duration_s')},
                   'references': [{**{k: r[k] for k in ('picture_index', 'asset_id', 'name', 'description', 'role', 'binding_notes')},
                                   'picture_tag':f'<Picture {r["picture_index"]}>','evidence_source':'saved_asset_description'}
                                  for r in shot['references']],
                   'reference_evidence':{'image_pixels_in_this_request':False,
                       'source':'Selected saved descriptions and binding notes; filenames and names are lookup aids, not pixel evidence.'},
                   'previous_shot_description': {'description': previous_text[:2000], 'truncated': len(previous_text) > 2000},
                   'continuity': shot['continuity'], 'dialogue': authored_dialogue(source)}
        timing=delivery_window(shot)
        if timing:payload['delivery_timing']=timing
        eye_view=re.search(r'\b(?:POV|first[-\u2010-\u2015 ]person)\b|\bunseen\b[^.\n]{0,60}\b(?:eye[- ]level|eyes)\b',shot['brief'],re.I)
        if eye_view and re.search(r'\b(?:strict|unseen|invisible)\b',shot['brief'],re.I):
            payload['viewpoint_constraints']={'required_prompt_direction':"Camera stays at the unseen observer's eyes, never behind the observer; no observer head, hair, neck, shoulders, back, torso, shadow or reflection appears.",
                'observer_visibility':'No unrequested observer hands; explicitly authored first-person hand actions may remain. Empty foreground, never over-the-shoulder.'}
        return shot, payload

    def refine_description(self, workspace, amendment=''):
        shot, payload = self._context(workspace)
        payload['request'] = amendment
        source=next(s for s in workspace['shots'] if s['id']==shot['shot_id'])
        dialogue=authored_dialogue(source,amendment)
        payload['dialogue']=dialogue
        bundle=load_rule_bundle('description_refine')
        instructions=bundle.text
        def validate(value):
            text = value.get('description')
            if not isinstance(text, str) or not text.strip():
                raise ValueError('Missing description.')
            validate_refinement(text,source,dialogue,amendment)
            return {'description': text.strip()}
        result = self.client.complete_json('description_refine', instructions, payload, validate=validate, shot_id=shot['shot_id'],rule_manifest=bundle.manifest())
        return {**result['value'], 'dialogue':dialogue, 'expected_revision': shot['revision'], 'timing': result['timing']}

    def write_prompt(self, workspace):
        shot, payload = self._context(workspace)
        if not shot['brief'].strip() or not shot['references']:
            raise ValueError('Enter a shot brief and select references first.')
        payload['required_picture_tags'] = [f'<Picture {ref["picture_index"]}>' for ref in shot['references']]
        payload['response_rules'] = 'Use every required_picture_tag literally inside subject_definitions or retention_analysis beside its matching asset. Asset names alone do not bind images.'
        bundle=load_rule_bundle('prompt_write')
        instructions=bundle.text
        original = copy.deepcopy(workspace)
        def validate(value):
            if set(value) != set(SECTION_KEYS):
                raise ValueError('Return exactly the six H3 section keys.')
            value = {key: re.sub(r'(?<![<\w])\b(Picture|Audio|Video)[ \t]+(\d+)\b(?!>)',
                lambda match: f'<{match.group(1)} {match.group(2)}>', text) if isinstance(text, str) else text
                for key, text in value.items()}
            trial = copy.deepcopy(original)
            current = next(s for s in trial['shots'] if s['id'] == shot['shot_id'])
            current.update(prompt_sections=value, prompt_basis=shot['inputs'], prompt_editor_dirty=False)
            checked = make_shot(json.dumps(trial))
            if not checked['prompt_ready']:
                raise ValueError('Candidate is not current.')
            validate_spoken_words(value,payload['dialogue'],shot['brief'])
            validate_speech_window(value,payload.get('delivery_timing'),payload['dialogue'])
            direction=payload.get('viewpoint_constraints',{}).get('required_prompt_direction')
            if direction and direction.replace('’',"'") not in value['detailed_description'].replace('’',"'"):
                raise ValueError('Include the required unseen observer direction verbatim in detailed_description: '+direction)
            return {key: value[key].strip() for key in SECTION_KEYS}
        result = self.client.complete_json('prompt_write', instructions, payload, validate=validate, shot_id=shot['shot_id'], max_tokens=4096,rule_manifest=bundle.manifest())
        return {'prompt_sections': result['value'], 'prompt_basis': shot['inputs'], 'expected_revision': shot['revision'], 'timing': result['timing']}
