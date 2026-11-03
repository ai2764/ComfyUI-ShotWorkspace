"""Select only output branches that actually depend on the chosen workbench."""
import copy
import urllib.parse
import urllib.request


def release_model(config):
    enabled = config.get('unload_before_generation', False)
    if type(enabled) is not bool:
        raise ValueError('Unload LLM before generation must be a boolean.')
    if not enabled:
        return
    url = config.get('unload_url', '').strip()
    if not url:
        raise ValueError('Set a model unload URL in LLM connection, or uncheck Unload LLM before generation.')
    source = urllib.parse.urlparse(config['base_url'])
    target = urllib.parse.urlparse(url)
    if target.username or target.password or target.query or target.fragment:
        raise ValueError('Model unload URL must not contain credentials, query parameters or fragments.')
    if (source.scheme, source.hostname, source.port) != (target.scheme, target.hostname, target.port):
        raise ValueError('The optional model unload URL must have the same origin as the LLM URL.')
    request = urllib.request.Request(url, data=b'', method='POST')
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def select_generation_branch(prompt, node_id, output_types):
    node_id = str(node_id)
    def links(value):
        if isinstance(value, list):
            if len(value) == 2 and isinstance(value[0], (str, int)) and isinstance(value[1], int) and str(value[0]) in prompt:
                yield str(value[0])
            else:
                for child in value:
                    yield from links(child)
        elif isinstance(value, dict):
            for child in value.values():
                yield from links(child)
    def ancestors(current, seen=None):
        seen = set() if seen is None else seen
        if current in seen:
            return seen
        seen.add(current)
        for parent in links(prompt[current].get('inputs', {})):
            ancestors(parent, seen)
        return seen
    outputs = []
    needed = set()
    for key, value in prompt.items():
        if value.get('class_type') in output_types:
            dependencies = ancestors(key)
            if node_id in dependencies:
                outputs.append(key)
                needed.update(dependencies)
    if not outputs:
        raise ValueError('No output is connected to this workbench. Connect it to your generation workflow first.')
    return {key: copy.deepcopy(value) for key, value in prompt.items() if key in needed}, outputs


def continuation_status(prompt):
    def linked(value):
        return (isinstance(value, list) and len(value) == 2
                and isinstance(value[0], (str, int))
                and type(value[1]) is int and value[1] >= 0
                and str(value[0]) in prompt)

    contexts = [n for n in prompt.values() if n.get('class_type') == 'MiniMaxH3MotionContext']
    active = False
    for context in contexts:
        data = context.get('inputs', {})
        for key in ('context_latent', 'context_frames'):
            link = data.get(key)
            if linked(link):
                source = prompt[str(link[0])]
                if source.get('class_type') == 'MiniMaxH3MotionContextLoadLatent' and source.get('inputs', {}).get('clip_index', 0) == 0:
                    continue
                active = True
    if active:
        return 'External Motion Context source connected; downstream graph owns its execution.'
    multiref_sources = {
        'MiniMaxH3StartMaskedContext': ('source_frames', 'live_starter_latent'),
        'MiniMaxH3GeneratedAVMaskedContext': ('source_latent',),
    }
    for node in prompt.values():
        keys = multiref_sources.get(node.get('class_type'), ())
        if any(linked(node.get('inputs', {}).get(key)) for key in keys):
            return ('External MultiRef context adapter is wired; the community workflow '
                    'selects the source and owns masks, timing and sampling.')
    return 'Standalone: no active Motion Context source detected. Authored previous-shot text does not guarantee visual continuation.'
