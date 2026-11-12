"""Optional, explicit transfer of a reviewed plan; never invokes a model."""
import copy
import hashlib
import json

FIELDS = ('version', 'assets', 'shots', 'active_shot_id', 'script', 'rough_idea',
          'story_title', 'story_target_duration_s', 'director_skill', 'director_skill_enabled',
          'prepared_example', 'story_development_timing', 'story_plan_timing')


def _revision(workspace):
    return hashlib.sha256(json.dumps(workspace, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def make_storyboard(storyboard_json):
    state = json.loads(storyboard_json)
    if state.get('version') != 1 or not isinstance(state.get('assets'), list) or not isinstance(state.get('shots'), list):
        raise ValueError('Expected a version1 storyboard with assets and shots.')
    if not state['shots']:
        raise ValueError('Plan and add shots before applying the storyboard.')
    ids = [s['id'] for s in state['shots']]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate storyboard shot IDs.')
    workspace = {key: copy.deepcopy(state[key]) for key in FIELDS if key in state}
    workspace['active_shot_id'] = ids[0]
    return {'schema': 'shot-storyboard/1', 'revision': _revision(workspace), 'workspace': workspace}


def require_applied_storyboard(workspace, storyboard=None):
    if storyboard is None:
        return
    if storyboard.get('schema') != 'shot-storyboard/1' or _revision(storyboard['workspace']) != storyboard.get('revision'):
        raise ValueError('Invalid storyboard packet.')
    if workspace.get('storyboard_source_revision') != storyboard['revision']:
        raise ValueError('Apply storyboard to the connected Shot Workspace before generating. The source plan has changed.')
