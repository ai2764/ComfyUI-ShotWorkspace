"""Explicit authoring and generation actions; sampling remains in the user's graph."""
import asyncio
import base64
import hashlib
import io
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web
from PIL import Image, ImageOps
import folder_paths
import nodes as comfy_nodes
from server import PromptServer

from .contract import make_shot
from .llm_runtime import LLMClient, AuthoringService
from .nodes import ShotWorkspace, image_path
from .generation import select_generation_branch, release_model, continuation_status

_operation_lock = asyncio.Lock()


def store_root():
    root = Path(folder_paths.get_user_directory()) / 'shot_workspace'
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_receipt(value):
    path = store_root() / 'jobs' / (value['prompt_id'] + '.json')
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def local_api(path, body=None):
    port = PromptServer.instance.port
    request = urllib.request.Request(f'http://127.0.0.1:{port}{path}',
        data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except Exception as exc:
        if hasattr(exc, 'read'):
            detail = exc.read().decode(errors='replace')[:4000]
            raise ValueError('ComfyUI rejected the graph: ' + detail) from exc
        raise


def describe_image(asset):
    path = image_path(asset['image'])
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
        image.thumbnail((768, 768))
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=85)
    return 'data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode()


def author(body, operation):
    service = AuthoringService(LLMClient(body['config'], store_root() / 'llm_calls.jsonl'))
    if operation == 'test':
        output = io.BytesIO()
        Image.new('RGB', (64, 64), (0, 64, 255)).save(output, format='PNG')
        return service.test_connection('data:image/png;base64,' + base64.b64encode(output.getvalue()).decode())
    if operation == 'analyse':
        asset = body['asset']
        signature = hashlib.sha256(image_path(asset['image']).read_bytes()).hexdigest()
        return {**service.describe_asset(asset, describe_image(asset)), 'content_sha256': signature}
    if operation == 'refine':
        return service.refine_description(body['workspace'], body.get('request', ''))
    if operation == 'write':
        return service.write_prompt(body['workspace'])
    raise ValueError('Unknown authoring operation.')


def video_files(value):
    found = []
    def walk(item):
        if isinstance(item, dict):
            if str(item.get('filename', '')).lower().endswith(('.mp4', '.webm', '.mov')):
                found.append({k: item[k] for k in ('filename', 'subfolder', 'type') if k in item})
            else:
                for child in item.values():
                    walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
    walk(value)
    return found



def register_routes():
    if getattr(PromptServer, 'instance', None) is None:
        return
    routes = PromptServer.instance.routes

    @routes.post('/shot-workspace/llm/{operation}')
    async def llm_action(request):
        try:
            body = await request.json()
            async with _operation_lock:
                host = urllib.parse.urlparse(body['config']['base_url']).hostname
                if host in {'127.0.0.1', 'localhost', '::1'}:
                    queue = await asyncio.to_thread(local_api, '/queue')
                    if queue.get('queue_running') or queue.get('queue_pending'):
                        raise ValueError('Finish video generation before using the local GPU LLM.')
                result = await asyncio.to_thread(author, body, request.match_info['operation'])
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({'error': str(exc)}, status=400)

    @routes.get('/shot-workspace/timings')
    async def timings(request):
        path = store_root() / 'llm_calls.jsonl'
        lines = path.read_text(encoding='utf-8').splitlines()[-500:] if path.exists() else []
        return web.json_response({'calls': [json.loads(line) for line in lines]})

    @routes.post('/shot-workspace/jobs')
    async def generate(request):
        try:
            body = await request.json()
            prompt = body['prompt']
            node_id = str(body['node_id'])
            if prompt.get(node_id, {}).get('class_type') != 'ShotWorkspace':
                raise ValueError('Select the workbench node in the submitted graph.')
            output_types = {name for name, value in comfy_nodes.NODE_CLASS_MAPPINGS.items() if getattr(value, 'OUTPUT_NODE', False)}
            prompt, output_ids = select_generation_branch(prompt, node_id, output_types)
            frozen = json.dumps(body['workspace'], ensure_ascii=False)
            snapshot = ShotWorkspace().capture(frozen)[0]
            if not snapshot['prompt_ready']:
                raise ValueError('Write a current prompt before generating.')
            queued_workspace = json.loads(frozen)
            queued_workspace['_queued_media_hashes'] = {str(ref['picture_index']): ref['content_sha256'] for ref in snapshot['references']}
            prompt[node_id]['inputs']['workspace_json'] = json.dumps(queued_workspace, ensure_ascii=False)
            receipt_context = {'shot_id': snapshot['shot_id'], 'revision': snapshot['revision']}
            async with _operation_lock:
                queue = await asyncio.to_thread(local_api, '/queue')
                if queue.get('queue_running') or queue.get('queue_pending'):
                    raise ValueError('Finish the current video before queueing another shot from this workbench.')
                await asyncio.to_thread(release_model, body['workspace'].get('llm_config', {}))
                queued = await asyncio.to_thread(local_api, '/prompt', {'prompt': prompt,
                    'extra_data': {'shot_workspace': receipt_context}})
            receipt = {**receipt_context, 'prompt_id': queued['prompt_id'], 'status': 'queued',
                       'queued_at': datetime.now(timezone.utc).isoformat(), 'snapshot': snapshot,
                       'continuation': continuation_status(prompt), 'output_node_ids': output_ids, 'outputs': []}
            write_receipt(receipt)
            return web.json_response(receipt)
        except Exception as exc:
            return web.json_response({'error': str(exc)}, status=400)

    @routes.get('/shot-workspace/jobs/{job_id}')
    async def job(request):
        job_id = request.match_info['job_id']
        if not re.fullmatch(r'[A-Za-z0-9-]{1,80}', job_id):
            raise web.HTTPBadRequest()
        path = store_root() / 'jobs' / (job_id + '.json')
        if not path.exists():
            raise web.HTTPNotFound()
        receipt = json.loads(path.read_text(encoding='utf-8'))
        if receipt['status'] in {'completed', 'failed', 'interrupted'}:
            return web.json_response(receipt)
        try:
            history = await asyncio.to_thread(local_api, '/history/' + job_id)
            entry = history.get(job_id)
            if entry:
                receipt['status'] = 'completed' if entry.get('status', {}).get('status_str') == 'success' else 'failed'
                owned = receipt.get('output_node_ids')
                values = entry.get('outputs', {})
                receipt['outputs'] = video_files({key: value for key, value in values.items() if owned is None or key in owned})
                messages = entry.get('status', {}).get('messages', [])
                times = {name: data.get('timestamp') for name, data in messages if isinstance(data, dict)}
                end = times.get('execution_success') or times.get('execution_error')
                start = times.get('execution_start')
                if start and end:
                    receipt['generation_ms'] = end - start
                for name, data in messages:
                    if name == 'execution_error':
                        receipt['error'] = data.get('exception_message', 'Generation failed.')
                write_receipt(receipt)
            else:
                queue = await asyncio.to_thread(local_api, '/queue')
                if any(row[1] == job_id for row in queue.get('queue_running', [])):
                    receipt['status'] = 'running'
                    receipt['missing_polls'] = 0
                elif any(row[1] == job_id for row in queue.get('queue_pending', [])):
                    receipt['status'] = 'queued'
                    receipt['missing_polls'] = 0
                else:
                    receipt['missing_polls'] = receipt.get('missing_polls', 0) + 1
                    if receipt['missing_polls'] >= 3:
                        receipt.update(status='interrupted', error='Job is no longer queued or running and has no completion history.')
                write_receipt(receipt)
            return web.json_response(receipt)
        except Exception as exc:
            return web.json_response({'error': str(exc)}, status=400)
