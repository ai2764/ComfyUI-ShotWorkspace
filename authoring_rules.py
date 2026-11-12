"""Conservative authored-speech extraction and known staging guards; no model calls."""
import math
import re

def delivery_window(shot):
    if not isinstance(shot['continuity'],dict):raise ValueError('Continuity must be an object.')
    config=shot['continuity'].get('delivery_timing')
    if config is None:return None
    if not isinstance(config,dict):raise ValueError('delivery_timing must be an object.')
    frames=config.get('prefix_trim_frames');fps=config.get('fps')
    if type(frames) is not int or not 0<=frames<shot['length'] or type(fps) not in (int,float) or fps!=shot['fps']:
        raise ValueError('Declare valid prefix_trim_frames and the actual workflow fps matching this shot.')
    lead=config.get('speech_lead_in_s',.35);tail=config.get('speech_tail_hold_s',.6)
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in [lead,tail]):
        raise ValueError('Speech lead-in and tail hold must be finite nonnegative seconds.')
    start=math.ceil((frames/fps+lead)*1000)/1000;end=math.floor((shot['length']/fps-tail)*1000)/1000
    if start>=end:raise ValueError('No retained speech window remains after context trim and speech guards.')
    return {'time_origin':'sampling_start_before_prefix_trim','prefix_trim_frames':frames,'fps':fps,
        'prefix_trim_s':frames/fps,'sampling_end_s':shot['length']/fps,'speech_start_s':start,'speech_end_s':end,
        'speech_lead_in_s':lead,'speech_tail_hold_s':tail}

def validate_speech_window(sections,window,dialogue):
    if not window or not dialogue:return
    text=sections['detailed_description']
    for block in _BLOCKS.finditer(text):
        interval=re.search(r'\[(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)s\]\s*[^<\n]{0,80}$',text[:block.start()])
        if not interval or not window['speech_start_s']<=float(interval[1])<float(interval[2])<=window['speech_end_s']:
            raise ValueError(f"Keep every complete spoken block in the retained speech window {window['speech_start_s']}–{window['speech_end_s']}s, before trimming. "
                'Immediately prefix each block with [start–ends] Speaker: <d>[Language] exact words</d>. Do not put new speech in the pinned prefix or final tail hold.')

_BLOCKS = re.compile(r'<d>\s*(?:\[[^\]]+\]\s*)?(.*?)</d>', re.S)
_QUOTED = r'''(?:"([^"\n]+)"|“([^”\n]+)”|'(.+?)'(?=\W|$)|‘(.+?)’(?=\W|$))'''
_SPEECH = re.compile(r'''(?:\b(?:says?|asks?|replies|reply|whispers?|shouts?|speaks?|dialogue|spoken\s+line|voice\s+is\s+heard)\b(?:(?:\s+in\s+\w+)|(?:\s+(?:directly\s+)?(?:to|into)\s+(?:the\s+)?(?:camera|frame|viewer|customer))){0,2}|台词|说道|回答|说|问)\s*[:,：，]?\s*''' + _QUOTED, re.I)
_PRINTED_SUBJECT=re.compile(r'\b(?:sign|label|poster|notice|caption|subtitle|photograph|photo|screen|printed text|book|page|note|letter|menu|card)\b(?:\s+(?!(?:and|but|then|while|who|as)\b)[\w\'-]+){0,6}\s*$|(?:标牌|招牌|字幕|标签|海报|照片)[^。！？\n]{0,20}$',re.I)
_CUES=re.compile(r'(?m)^\s*(?:[^\n:\[\]]{1,80})?\[[^\]\n]{1,32}\]\s*:\s*([^\n]+)$')

def normalized(text):
    return ' '.join(str(text).replace('’', "'").replace('‘', "'").replace('“','"').replace('”','"').split())

def speech_lines(value):
    if not isinstance(value,str):raise ValueError('Dialogue must be a plain string.')
    blocks=_BLOCKS.findall(value)
    if blocks:return [line.strip() for line in blocks if line.strip()]
    result=[]
    for line in value.splitlines():
        # Preserve the words; a speaker/language cue is metadata, not spoken text.
        line=re.sub(r'^\s*(?:[^\n:]{1,80}\s*)?\[[^\]]+\]\s*:?\s*','',line).strip()
        if line:result.append(line)
    return result

def authored_dialogue(source,amendment=''):
    explicit=source.get('dialogue','')
    if explicit:
        speech_lines(explicit)
        return explicit.strip()
    found=[]
    for text in [source.get('brief',''),amendment]:
        entries=[(m.start(),m.group(1).strip()) for m in _BLOCKS.finditer(text) if m.group(1).strip()]
        outside=_BLOCKS.sub(lambda match:' '*len(match.group(0)),text)
        for match in _CUES.finditer(outside):
            if match.group(1).strip():entries.append((match.start(),match.group(1).strip()))
        outside=_CUES.sub(lambda match:' '*len(match.group(0)),outside)
        for match in _SPEECH.finditer(outside):
            prefix=outside[max(0,match.start()-100):match.start()]
            if re.search(r'\b(?:no|not|never|avoid|without)\s*(?:\w+\s+){0,2}$',prefix,re.I):continue
            if _PRINTED_SUBJECT.search(prefix):continue
            entries.append((match.start(),next(group for group in match.groups() if group is not None).strip()))
        found.extend(line for _,line in sorted(entries))
    return '\n'.join(found)

def _unquote(text):
    text=normalized(text)
    if len(text)>1 and text[0] in ['"',"'"] and text[-1]==text[0]:return text[1:-1].strip()
    return text

def _affirmative(text,pattern):
    return [m for m in pattern.finditer(text) if not re.search(r'\b(?:no|not|never|avoid|without)\b',re.split(r'[.!?\n]',text[:m.start()])[-1][-32:],re.I)]

_BACKGROUND=re.compile(r'\b(?:background\s+(?:chatter|voices|conversations)|(?:distant|occasional|faint)\s+(?:chatter|conversations|voices)|murmur(?:ing|s)?\s+of\s+(?:customers|people|voices)|customers?\s+(?:chatting|murmuring))\b',re.I)

def validate_spoken_words(sections,dialogue,source_text=''):
    text='\n'.join(sections.values());blocks=_BLOCKS.findall(text)
    if _affirmative(_BLOCKS.sub('',text),_BACKGROUND) and not _affirmative(source_text,_BACKGROUND):
        raise ValueError('overall_soundscape: Remove invented background customer speech/chatter; use only nonvocal ambience and authored physical sounds.')
    if authored_dialogue({'brief':_BLOCKS.sub('',text)}):
        raise ValueError('Keep spoken dialogue only inside <d> blocks; do not add speech outside them.')
    if not dialogue:
        if blocks or '<d>' in text:raise ValueError('Invented dialogue is not allowed.')
        return
    if text.count('<d>')!=len(blocks):raise ValueError('Malformed dialogue blocks.')
    expected=normalized(' '.join(_unquote(line) for line in speech_lines(dialogue)))
    actual=normalized(' '.join(_unquote(block) for block in blocks))
    if not actual or actual!=expected:
        raise ValueError('Preserve every authored dialogue word in order; do not add, omit or paraphrase speech. '
            'Expected spoken text: '+repr(expected)+'. Put speaker names outside <d> blocks and language metadata inside square brackets, as in <d>[English] exact words</d>.')
    if any('<d>' in value for key,value in sections.items() if key!='detailed_description'):
        raise ValueError('Spoken dialogue belongs only in detailed_description.')

_CUSTOMER_BEHIND=re.compile(r'\b(?:customer|viewer|camera)\s+(?:(?:is|was|standing|stands?|sitting|sits?|positioned|located|remains?|stays?|seated|directly|just|now|still)\s+){0,6}behind\b[^.!?\n]{0,50}\bcounter\b',re.I)

def validate_refinement(description,source,dialogue,amendment=''):
    for line in speech_lines(dialogue):
        if normalized(line) not in normalized(description):raise ValueError('Preserve the exact authored dialogue in the description.')
    candidate=authored_dialogue({'brief':description})
    expected=normalized(' '.join(_unquote(line) for line in speech_lines(dialogue)))
    actual=normalized(' '.join(_unquote(line) for line in speech_lines(candidate)))
    if actual!=expected:
        raise ValueError('Preserve the exact authored dialogue; do not expand, repeat or add speech in the description. '
            'Expected spoken text: '+repr(expected)+'. Put speaker names outside <d> blocks, not inside the spoken text. '
            'For example: Alex: <d>exact words</d>. Return the corrected complete description.')
    original=source.get('brief','')+'\n'+amendment
    if _affirmative(description,_CUSTOMER_BEHIND) and not _affirmative(original,_CUSTOMER_BEHIND):
        raise ValueError('Do not change staging by moving the customer/viewer/camera behind the counter.')
    if re.search(r'\b(?:POV|first[-\u2010-\u2015 ]person)\b',original,re.I):
        phrase=re.compile(r'over[- ]the[- ]shoulder|third[- ]person',re.I)
        if not phrase.search(original):
            for match in phrase.finditer(description):
                if not re.search(r'\b(?:no|not|never|avoid|without)\b',description[max(0,match.start()-24):match.start()],re.I):
                    raise ValueError('Preserve the authored first-person POV; do not add a third-person or over-the-shoulder view.')
