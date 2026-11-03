"""Timing declaration for the verified native H3 22-frame continuation template.

Call before /write. Does not connect nodes, approve prompts or queue generation.
Source frame count/fps must come from video metadata or the native latent layout.
"""
import copy

def with_h3_delivery_timing(workspace,graph,context_kind,*,source_frames,source_fps):
    if context_kind not in ('video','latent'):raise ValueError('Use video or latent continuation.')
    contexts=[(key,n) for key,n in graph.items() if n['class_type']=='MiniMaxH3MotionContext']
    trims=[n for n in graph.values() if n['class_type']=='MiniMaxH3MotionContextTrim']
    if len(contexts)!=1 or len(trims)!=1:raise ValueError('Expected one native context and one matching trim node.')
    key,node=contexts[0]
    if str(node['inputs'].get('context_length'))!='22' or trims[0]['inputs'].get('trim_frames')!=[key,1]:
        raise ValueError('This adapter certifies only the native linked 22-frame trim template.')
    if type(source_frames) is not int or source_frames<22 or source_fps!=24:
        raise ValueError('Verify at least 22 source frames at 24fps before declaring this timing.')
    def linked(value):return isinstance(value,list) and len(value)==2 and str(value[0]) in graph and type(value[1]) is int and value[1]>=0
    port='context_frames' if context_kind=='video' else 'context_latent'
    if not linked(node['inputs'].get(port)) or (context_kind=='video' and linked(node['inputs'].get('context_latent'))):
        raise ValueError('The declared continuation kind must have an active native context input.')
    fps=trims[0]['inputs'].get('fps',24)
    if linked(fps):
        kind=graph[str(fps[0])]['class_type'];slot=fps[1]
        own_video_fps=(kind,slot)==('GetVideoComponents',2) and context_kind=='video' and node['inputs']['context_frames']==[fps[0],0]
        fps=24 if (kind,slot) in [('ShotWorkspace',6),('ShotWorkspaceInterface',5)] or own_video_fps else None
    if fps!=24:raise ValueError('Resolve the native trim fps to the verified 24fps source before declaring timing.')
    result=copy.deepcopy(workspace)
    shot=next(s for s in result['shots'] if s['id']==result['active_shot_id'])
    shot['continuity']={**shot.get('continuity',{}),'mode':'external_workflow',
        'delivery_timing':{'prefix_trim_frames':22,'fps':24,'speech_lead_in_s':.35,'speech_tail_hold_s':.6}}
    return result
