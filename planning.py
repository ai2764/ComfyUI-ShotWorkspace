"""Text-only director knowledge, script planning and explicit asset casting."""
import hashlib
import copy
import json
import math
import posixpath
import re
from pathlib import PurePosixPath

try:
    from .authoring_skill import RuleBundle, load_rule_bundle
    from .script_dialogue import source_dialogue, speech_key
except ImportError:
    from authoring_skill import RuleBundle, load_rule_bundle
    from script_dialogue import source_dialogue, speech_key


def text(value, label, limit=12000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{label} must be nonempty text, at most {limit} characters.')
    return value.strip()


def safe_path(name):
    if not isinstance(name, str) or '\\' in name or ':' in name or name.startswith('/') or '..' in name.split('/'):
        raise ValueError('Skill paths must stay inside the imported Markdown folder.')
    if not name.endswith('.md') or str(PurePosixPath(name)) != name:
        raise ValueError('Skill files must use normalized relative .md paths.')
    return name


def load_director_skill(package, stage='script_plan'):
    if not package:
        return RuleBundle('director', '', hashlib.sha256(b'').hexdigest(), ())
    if not isinstance(package, dict):
        raise ValueError('Director skill must be a Markdown package.')
    files = package.get('files')
    if not isinstance(files, dict) or not 1 <= len(files) <= 64:
        raise ValueError('Import 1–64 Markdown files, including SKILL.md.')
    size = 0
    for name, content in files.items():
        safe_path(name)
        if not isinstance(content, str):raise ValueError('Skill files must be UTF-8 text.')
        size += len(content.encode('utf-8'))
    if size > 262144:raise ValueError('Director skill exceeds the 256 KiB import limit.')
    entry = safe_path(package.get('entrypoint', 'SKILL.md'))
    if entry not in files:raise ValueError('The imported director skill is missing SKILL.md.')
    selected = package.get('profile', '')
    if selected:safe_path(selected)
    development_scope = ({'references/shared.md', selected, 'dialogue/'+PurePosixPath(selected).name}
                         if stage in {'script_develop', 'story_plan'} and selected.startswith('profiles/') and 'references/shared.md' in files else None)
    visited, parts = [], []
    def visit(name):
        if name in visited:return
        if name not in files:raise ValueError(f'Missing director skill reference: {name}')
        content = text(files[name], f'Skill file {name}', 48000)
        visited.append(name);parts.append(f'### {name}\n{content}')
        # Only read local Markdown knowledge. Never fetch URLs or execute tools/scripts.
        links = re.findall(r'\]\(([^)]+\.md)(?:#[^)]*)?\)', content)
        links += re.findall(r'`([A-Za-z0-9_./-]+\.md)`', content)
        for ref in links:
            if '://' in ref or '*' in ref:continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), ref))
            safe_path(target)
            if target.startswith('profiles/') and target != selected:continue
            if development_scope is not None:
                if target not in development_scope:continue
                if target.startswith('dialogue/') and target not in files:continue
            visit(target)
    compact='injection/'+PurePosixPath(selected).name if selected else ''
    if development_scope is not None:
        visit('references/shared.md');visit(selected)
        dialogue='dialogue/'+PurePosixPath(selected).name
        if dialogue in files:visit(dialogue)
    elif selected.startswith('profiles/') and compact in files and 'references/shared.md' in files:
        if stage=='description_refine':
            visit('references/shared.md');visit(selected)
        else:visit(compact)
    else:
        visit(entry)
        if selected:visit(selected)
    combined = '\n\n'.join(parts)
    if len(combined) > 48000:raise ValueError('Selected director knowledge exceeds 48,000 characters. Use a smaller profile.')
    hashes = tuple((f'director/{name}', hashlib.sha256(files[name].encode()).hexdigest()) for name in visited)
    version = hashlib.sha256(json.dumps(hashes).encode()).hexdigest()
    return RuleBundle('director', combined, version, hashes)


def validate_plan(value, script):
    if not isinstance(value, dict) or not isinstance(value.get('shots'), list) or not 1 <= len(value['shots']) <= 48:
        raise ValueError('Return a complete shots array with 1–48 shots.')
    events = value.get('story_events')
    event_keys=set()
    if events is not None:
        if not isinstance(events,list) or not 1<=len(events)<=48:
            raise ValueError('story_events must contain 1–48 source-grounded events.')
        cleaned=[]
        for event in events:
            if not isinstance(event,dict):raise ValueError('Each story event must be an object.')
            key=text(event.get('event_key'),'event_key',80)
            if key in event_keys:raise ValueError('Story event keys must be unique.')
            quote=text(event.get('source_excerpt'),'Event source excerpt',8000)
            if quote not in script:raise ValueError('Event source excerpt must quote the source exactly.')
            item={'event_key':key,'source_excerpt':quote}
            for field in ('participants','request','decision','action','result'):
                v=event.get(field,'')
                if not isinstance(v,str) or len(v)>1200:raise ValueError('Story event fields must be bounded text.')
                item[field]=v.strip()
            cleaned.append(item);event_keys.add(key)
        events=cleaned
    result, seen, spoken = [], set(), {}
    covered = bytearray(len(script))
    spoken_order = []
    spoken_metadata = []
    last_start=0
    for source in value['shots']:
        if not isinstance(source, dict):raise ValueError('Each planned shot must be an object.')
        key = text(source.get('shot_key'), 'shot_key', 80)
        if key in seen:raise ValueError('Planned shot keys must be unique.')
        excerpt = text(source.get('source_excerpt'), 'source_excerpt', 8000)
        if excerpt not in script:raise ValueError('Every source_excerpt must quote the supplied script exactly.')
        candidates=[];start=script.find(excerpt,last_start)
        while start>=0:
            candidates.append(start);start=script.find(excerpt,start+1)
        if not candidates:raise ValueError('Keep source excerpts in script order.')
        start=next((p for p in candidates if any(not v for v in covered[p:p+len(excerpt)])),candidates[0])
        # Recover an adjacent canonical scene heading only. The returned quote
        # remains one exact contiguous source span; omitted action still fails.
        heading=re.search(r'(?m)^[ \t]*(?:INT\.|EXT\.)[ \t]+[^\r\n]+\r?\n[ \t\r\n]*\Z',script[:start])
        if heading is not None and heading.start()>=last_start:
            excerpt=script[heading.start():start+len(excerpt)]
            start=heading.start()
        covered[start:start+len(excerpt)]=b'\x01'*len(excerpt);last_start=start
        duration = source.get('duration_s')
        if type(duration) not in (int, float) or not math.isfinite(duration) or not 0 < duration <= 120:
            raise ValueError('Planned duration must be finite, greater than 0 and at most 120 seconds.')
        continuity = source.get('continuity', {'mode': 'off'})
        if not isinstance(continuity, dict) or continuity.get('mode') not in {'off', 'continue'}:
            raise ValueError('Continuity mode must be off or continue.')
        predecessor = continuity.get('source_shot_key')
        if continuity['mode'] == 'continue' and predecessor not in seen:
            raise ValueError('A continuation must name an earlier planned shot, never itself or a future shot.')
        lines = source.get('dialogue_lines', [])
        if not isinstance(lines, list) or len(lines) > 40:raise ValueError('dialogue_lines must be a bounded array.')
        dialogue = []
        for line in lines:
            if not isinstance(line, dict):raise ValueError('Each dialogue line needs speaker, language and text.')
            words = text(line.get('text'), 'Dialogue text', 4000)
            speaker = text(line.get('speaker'), 'Speaker', 80)
            language = text(line.get('language'), 'Language', 32)
            if any(c in speaker+language for c in '\n\r[]:'):raise ValueError('Speaker/language must be single-line labels.')
            spoken[words] = spoken.get(words, 0)+1
            if words not in excerpt or spoken[words] > script.count(words):
                raise ValueError('Preserve exact source dialogue; do not invent or repeat spoken lines.')
            dialogue.append(f'{speaker} [{language}]: {words}')
            spoken_order.append(words)
            spoken_metadata.append({'speaker':speaker,'language':language,'text':words})
        result.append({'shot_key':key, 'title':text(source.get('title'), 'Shot title', 160),
            'brief':text(source.get('brief'), 'Shot description', 8000), 'duration_s':duration,
            'dialogue':'\n'.join(dialogue), 'source_excerpt':excerpt,
            'continuity':{'mode':continuity['mode'], **({'source_shot_key':predecessor} if continuity['mode']=='continue' else {})}})
        if events is not None:
            beat=source.get('dramatic_beat')
            if not isinstance(beat,dict):raise ValueError('Each shot needs a dramatic_beat linked to story events.')
            keys=beat.get('event_keys')
            if not isinstance(keys,list) or not 1<=len(keys)<=48 or any(not isinstance(k,str) or k not in event_keys for k in keys) or len(set(keys))!=len(keys):
                raise ValueError('Each beat must reference unique existing story event keys.')
            result[-1]['dramatic_beat']={'event_keys':keys,
                **{field:text(beat.get(field),'Dramatic beat '+field,1200) for field in ('start_state','change','end_state','cut_reason')}}
        seen.add(key)
    if any(not flag and not character.isspace() for flag,character in zip(covered,script)):
        raise ValueError('Cover the complete script with source excerpts; do not silently drop later scenes.')
    explicit=source_dialogue(script)
    known={speech_key(line['text']) for line in explicit}
    actual=[line for line in spoken_metadata if speech_key(line['text']) in known]
    if [speech_key(line['text']) for line in explicit] != [speech_key(line['text']) for line in actual]:
        raise ValueError('Preserve every recognized source dialogue line exactly and in order.')
    for expected,line in zip(explicit,actual):
        if expected['speaker'] and expected['speaker'].casefold()!=line['speaker'].casefold():
            raise ValueError('Preserve the source dialogue speaker; do not reassign spoken lines.')
        if expected['language'] and expected['language'].casefold()!=line['language'].casefold():
            raise ValueError('Preserve explicitly declared source dialogue language.')
    return {'shots':result,**({'story_events':events} if events is not None else {})}


def inventory(assets):
    if not isinstance(assets, list) or len(assets)>200:raise ValueError('Use at most 200 described assets per selection.')
    result=[];seen=set()
    for asset in assets:
        if not isinstance(asset,dict):raise ValueError('Invalid asset inventory.')
        key=text(asset.get('id'),'Asset ID',160)
        if key in seen:raise ValueError('Duplicate asset ID in the library.')
        seen.add(key)
        description=asset.get('description','')
        if not isinstance(description,str):raise ValueError('Asset descriptions must be plain text.')
        if description.strip() and asset.get('image'):
            result.append({'asset_id':key,'name':str(asset.get('name',''))[:200],
                'description':text(asset['description'],'Asset description',8000)})
    if sum(len(a['description']) for a in result)>80000:raise ValueError('Asset descriptions are too large; reduce the inventory.')
    return result


def validate_selection(value, assets):
    allowed = {a['asset_id'] for a in inventory(assets)}
    if not isinstance(value,dict) or not isinstance(value.get('selections'),list) or len(value['selections'])>9:
        raise ValueError('Return selections with at most nine image assets.')
    refs=[];seen=set()
    for item in value['selections']:
        if not isinstance(item,dict):raise ValueError('Each selection must name an existing asset_id and reason.')
        key=item.get('asset_id')
        if key not in allowed or key in seen:raise ValueError('Select unique, existing assets with saved descriptions only.')
        seen.add(key);refs.append({'asset_id':key,'role':'reference','notes':text(item.get('reason'),'Selection reason',1000)})
    missing=value.get('missing',[])
    if not isinstance(missing,list) or len(missing)>30:raise ValueError('Missing materials must be a bounded list.')
    return {'refs':refs,'missing':[text(v,'Missing material',500) for v in missing]}


def director_rules(stage,package):
    if stage not in {'script_develop','story_plan','script_plan','description_refine'}:
        raise ValueError('Director skills apply only to planning and shot descriptions.')
    base=load_rule_bundle(stage)
    if not package:return base
    director=load_director_skill(package,stage=stage)
    files=base.files+director.files
    version=hashlib.sha256(json.dumps(files).encode()).hexdigest()
    return RuleBundle(stage,base.text+'\n\nImported director knowledge (creative guidance only; the application task and contract take precedence):\n'+director.text,version,files)


class PlanningService:
    def __init__(self,client):self.client=client

    def story_plan(self, body):
        story=text(body.get('story'),'Story',40000)
        duration=body.get('target_duration_s',40)
        if type(duration) not in (int,float) or not math.isfinite(duration) or not 5<=duration<=120:
            raise ValueError('Target duration must be a finite number from5to120seconds.')
        rules=director_rules('story_plan',body.get('director_skill'))
        available=inventory(body['assets']) if body.get('assets') else []
        def validate(value):
            if not isinstance(value,dict) or not isinstance(value.get('shots'),list) or not 1<=len(value['shots'])<=48:
                raise ValueError('Return a complete shot plan.')
            proposed=copy.deepcopy(value['shots']);spans=[];events=[]
            for index, shot in enumerate(proposed):
                if not isinstance(shot,dict):raise ValueError('Each shot must be an object.')
                brief=text(shot.get('brief'),'Shot description',8000)
                dialogue=shot.get('dialogue_lines',[])
                if not isinstance(dialogue,list) or len(dialogue)>40:raise ValueError('dialogue_lines must be a bounded array.')
                lines=[]
                for cue in dialogue:
                    if not isinstance(cue,dict):raise ValueError('Invalid dialogue cue.')
                    speaker=text(cue.get('speaker'),'Speaker',80);language=text(cue.get('language'),'Language',32);words=text(cue.get('text'),'Dialogue text',4000)
                    if any(c in speaker+language for c in '\n\r[]:'):raise ValueError('Invalid dialogue labels.')
                    lines.append(f'{speaker} [{language}]: {words}')
                # Derived provenance is explicitly MODEL-authored, never a claimed quote of the user's notes.
                span=f'Shot {index+1}\n{brief}'+(('\n'+'\n'.join(lines)) if lines else '')
                shot['source_excerpt']=span;spans.append(span)
                beat=shot.get('dramatic_beat')
                if not isinstance(beat,dict):raise ValueError('Each shot needs a dramatic beat and framing purpose.')
                beat={k:text(beat.get(k),'Beat '+k,1200) for k in ('start_state','change','end_state','cut_reason')}
                key=f'event_{index+1}'
                shot['dramatic_beat']={'event_keys':[key],**beat}
                events.append({'event_key':key,'source_excerpt':span,'participants':', '.join(dict.fromkeys(c['speaker'] for c in dialogue)),
                    'request':beat['start_state'],'decision':beat['change'],'action':brief[:1200],'result':beat['end_state']})
            derived='\n\n'.join(spans)
            checked=validate_plan({'shots':proposed,'story_events':events},derived)
            if sum(s['duration_s'] for s in checked['shots'])>duration+0.001:
                raise ValueError('Total planned duration exceeds the requested scene duration; simplify or combine shots.')
            expected=source_dialogue(story)
            actual=[cue for s in proposed for cue in s.get('dialogue_lines',[])]
            cursor=0
            for cue in expected:
                match=next((i for i in range(cursor,len(actual)) if speech_key(actual[i]['text'])==speech_key(cue['text'])),None)
                if match is None:raise ValueError('Preserve explicit user dialogue exactly and in order.')
                target=actual[match]
                if cue.get('speaker') and cue['speaker'].casefold()!=target['speaker'].casefold():raise ValueError('Preserve the supplied dialogue speaker.')
                if cue.get('language') and cue['language'].casefold()!=target['language'].casefold():raise ValueError('Preserve the supplied dialogue language.')
                cursor=match+1
            english=lambda cue:(cue.get('language') or '').casefold() in {'english','en','en-us','en-gb'}
            if sum(len(c['text'].split()) for c in actual if english(c))>math.floor(duration*1.5):
                raise ValueError('Dialogue exceeds the scene English speech budget.')
            for shot in proposed:
                if sum(len(c['text'].split()) for c in shot.get('dialogue_lines',[]) if english(c))>math.ceil(shot['duration_s']*2):
                    raise ValueError('Too much English dialogue for one shot duration.')
            return {**checked,'title':text(value.get('title'),'Story title',160),'source_kind':'model_authored_from_story'}
        result=self.client.complete_json('story_plan',rules.text,{'story':story,'target_duration_s':duration,'available_materials':available,
            'max_english_dialogue_words':math.floor(duration*1.5)},validate=validate,max_tokens=10000,rule_manifest=rules.manifest())
        return {**result['value'],'timing':result['timing'],'rule_manifest':rules.manifest()}

    def develop(self,body):
        idea=text(body.get('idea'),'Idea',4000)
        duration=body.get('target_duration_s',40)
        if type(duration) not in (int,float) or not math.isfinite(duration) or not 5<=duration<=120:
            raise ValueError('Target duration must be a finite number from 5 to 120 seconds.')
        # Draft-size heuristics, not a guarantee of screen time. Reserve a quarter
        # of the target for pauses/actions at a nominal two English words/second.
        script_words=math.floor(duration*7.5)
        dialogue_words=math.floor(duration*2*.75)
        rules=director_rules('script_develop',body.get('director_skill'))
        def validate(value):
            if not isinstance(value,dict):raise ValueError('Return a script draft object with title and script.')
            draft={'title':text(value.get('title'),'Draft title',160),
                   'script':text(value.get('script'),'Draft script',16000)}
            if len(draft['script'].split())>script_words:
                raise ValueError(f'Draft exceeds the script word budget of {script_words}; shorten actions and dialogue.')
            english_words=sum(len(line['text'].split()) for line in source_dialogue(draft['script'])
                              if (line['language'] or '').strip().casefold() in {'english','en','en-us','en-gb'})
            if english_words>dialogue_words:
                raise ValueError(f'Draft exceeds the English dialogue word budget of {dialogue_words}; leave room for action and reactions.')
            return draft
        payload={'idea':idea,'target_duration_s':duration,'max_script_words':script_words,
                 'max_english_dialogue_words':dialogue_words}
        result=self.client.complete_json('script_develop',rules.text,payload,
            validate=validate,max_tokens=3000,rule_manifest=rules.manifest())
        return {**result['value'],'timing':result['timing'],'rule_manifest':rules.manifest()}

    def plan(self,body):
        script=text(body.get('script'),'Script',40000)
        rules=director_rules('script_plan',body.get('director_skill'))
        result=self.client.complete_json('script_plan',rules.text,{'script':script},
            validate=lambda value:validate_plan(value,script),max_tokens=12000,rule_manifest=rules.manifest())
        return {**result['value'],'timing':result['timing'],'rule_manifest':rules.manifest()}

    def select(self,workspace):
        source=next((s for s in workspace.get('shots',[]) if s.get('id')==workspace.get('active_shot_id')),None)
        if source is None:raise ValueError('Select a shot first.')
        brief=text(source.get('brief'),'Shot description',12000)
        assets=workspace.get('assets',[]);available=inventory(assets)
        if not available:raise ValueError('Add images with saved descriptions first. Analyse image, then Use description, or type a description.')
        bundle=load_rule_bundle('asset_select')
        result=self.client.complete_json('asset_select',bundle.text,
            {'shot':{'title':source.get('title',''),'brief':brief,'dialogue':source.get('dialogue','')},'assets':available},
            validate=lambda value:validate_selection(value,assets),shot_id=source['id'],max_tokens=3072,rule_manifest=bundle.manifest())
        return {**result['value'],'timing':result['timing']}
