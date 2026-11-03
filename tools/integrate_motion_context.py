"""Add an external authoring boundary without rearranging the author's canvas."""
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from workflow_compat import Graph

SOURCE = ROOT / 'examples/upstream/motion-context/H3-Motion-Context-v0.7.json'
COMMIT = '518c083d11d80fa5920222ad89889924ee4401c9'
SOURCE_SHA256 = '0c33daa8da99001f6b716f251667ad01e4b3471351081426f7535478d3ee2800'


def integrate(original, workspace):
    result = copy.deepcopy(original)
    graph = Graph(result)
    template = json.loads((ROOT / 'examples/interface-preview.json').read_text(encoding='utf-8'))
    author = copy.deepcopy(next(n for n in template['nodes'] if n['type'] == 'ShotWorkspace'))
    author.update(pos=[-5680, 4400], size=[1120, 1100], title='Shot Workspace')
    author['widgets_values'] = [json.dumps(workspace, ensure_ascii=False)]
    author_id = graph.add(author)
    outputs = [('prompt', 'STRING'), ('duration_s', 'FLOAT'), ('width', 'INT'), ('height', 'INT'), ('frame_count', 'INT'), ('fps', 'FLOAT')]
    outputs += [(f'image_{i}', 'IMAGE') for i in range(1, 10)]
    interface_id = graph.add({'type': 'ShotWorkspaceInterface', 'title': 'Workflow Interface',
        'pos': [-3610, 4800], 'size': [300, 380], 'order': 0, 'mode': 0, 'flags': {},
        'inputs': [{'name': 'shot', 'type': 'SHOT', 'link': None}],
        'outputs': [{'name': name, 'type': kind, 'links': []} for name, kind in outputs],
        'properties': {'Node name for S&R': 'ShotWorkspaceInterface'}, 'widgets_values': [],
        'color': '#30434b', 'bgcolor': '#202a2f'})
    graph.connect(author_id, 0, interface_id, 'shot', 'SHOT')
    # Preserve the author's canvas/frame controls. Only prompt and Picture 1 enter here.
    graph.connect(interface_id, 0, 503, 'prompt', 'STRING')
    graph.connect(interface_id, 6, 503, 'ref_images.ref_image_0', 'IMAGE')
    result['groups'] += [
        {'title': 'Shot Workspace', 'bounding': [-5710, 4330, 1180, 1210], 'color': '#3f4952', 'font_size': 24, 'flags': {}},
        {'title': 'Workflow Interface', 'bounding': [-3650, 4720, 380, 470], 'color': '#496673', 'font_size': 24, 'flags': {}}]
    result.setdefault('extra', {})['workflow_interface'] = {
        'source_repo': 'NikoDemon80/ComfyUI-H3-Motion-Context', 'source_commit': COMMIT,
        'source_file': 'example_workflows/H3-Motion-Context-v0.7.json',
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'entry_points': [{'node': 503, 'input': 'prompt'}, {'node': 503, 'input': 'ref_images.ref_image_0'}],
        'unmodified_controls': 'Original model loaders, sampler, canvas, length, fps, Motion Context, decode and output settings',
        'license': 'GPL-3.0', 'scope': 'Connection/layout template; not a successful-generation claim'}
    return result


def audit(original, connected):
    new_nodes = {n['id']: n for n in connected['nodes']}
    changes = []
    for node in original['nodes']:
        old, new = copy.deepcopy(node), copy.deepcopy(new_nodes[node['id']])
        for value in (old, new):
            for port in value.get('inputs', []): port.pop('link', None)
            for port in value.get('outputs', []): port.pop('links', None)
        if old != new: changes.append(node['id'])
    old_links = {l[0]: l for l in original['links']}
    new_links = {l[0]: l for l in connected['links']}
    removed = [key for key in old_links if key not in new_links]
    return {'original_nodes': len(original['nodes']), 'changed_node_definitions': changes,
        'original_groups_unchanged': connected['groups'][:len(original['groups'])] == original['groups'],
        'subgraphs_unchanged': connected.get('definitions') == original.get('definitions'),
        'removed_input_links': removed,
        'changed_retained_links': [key for key in old_links.keys() & new_links.keys() if old_links[key] != new_links[key]],
        'new_graph_issues': Graph(connected).issues()}


