"""Conservative source dialogue metadata for prose and common screenplay cues."""
import re
from collections import Counter
try:
    from .authoring_rules import authored_dialogue, speech_lines
except ImportError:
    from authoring_rules import authored_dialogue, speech_lines


def speech_key(value):
    value=' '.join(value.replace('’',"'").replace('‘',"'").replace('“','"').replace('”','"').split())
    return value[1:-1].strip() if len(value)>1 and value[0]==value[-1] and value[0] in '\"\'' else value


def source_dialogue(script):
    found=[]
    non_speakers={'DAY','NIGHT','LATER','FLASHBACK','FADE IN','FADE OUT','CUT TO','SIGN','LABEL','POSTER','CAPTION','SUBTITLE','ON SCREEN','SCREEN TEXT'}
    def scene_header(line):
        return line in non_speakers or line.startswith(('SCENE ','CHAPTER ','TITLE ','INT.','EXT.','INT ','EXT '))
    # Explicit Speaker [Language]: words, or Speaker: "words".
    cue=re.compile(r"(?m)^[ \t]*(?P<speaker>[\w'-]+(?:[ \t]+[\w'-]+){0,2})[ \t]*(?:\[(?P<language>[^\]\n]+)\])?[ \t]*:[ \t]*(?P<words>[^\n]+)$")
    for m in cue.finditer(script):
        words=m['words'].strip();speaker=m['speaker'].strip()
        if re.search(r'\b(?:says?|asks?|replies|whispers?|shouts?)$',speaker,re.I):continue
        if scene_header(speaker.upper()) or speaker.startswith('场景'):continue
        if not m['language'] and not words.startswith(('"','“',"'",'‘')):continue
        found.append({'start':m.start(),'speaker':speaker,'language':m['language'],'text':speech_key(words)})
    prose=re.compile(r'(?P<speaker>[A-Z][\w\'-]*(?:[ \t]+[A-Z][\w\'-]*){0,2})\s+(?i:says?|asks?|replies|whispers?|shouts?)'
        r'(?:\s+(?i:in)\s+(?P<language>[A-Za-z-]+))?\s*[:：]?\s*["“](?P<words>[^"”\n]+)["”]')
    for m in prose.finditer(script):
        speaker=re.sub(r'^(?:Then|Now|Suddenly|Finally|Meanwhile|Later|Next|As|When)\s+','',m['speaker'])
        found.append({'start':m.start(),'speaker':speaker,'language':m['language'],'text':m['words']})
    # Conventional uppercase character cue followed by a dialogue paragraph.
    rows=script.splitlines(keepends=True);offsets=[];offset=0
    for row in rows:offsets.append(offset);offset+=len(row)
    def heading(line):
        if scene_header(line):return False
        return bool(re.fullmatch(r"[A-Z][A-Z '\-]{0,59}(?:\s+\([A-Z. ]+\))?",line))
    i=0
    while i<len(rows):
        label=rows[i].strip()
        if not heading(label):i+=1;continue
        j=i+1;words=[]
        while j<len(rows):
            line=rows[j].strip()
            if not line or heading(line) or scene_header(line):break
            if not (line.startswith('(') and line.endswith(')')):words.append(line)
            j+=1
        if words:
            found.append({'start':offsets[i],'speaker':re.sub(r'\s+\([^)]*\)$','',label),'language':None,'text':' '.join(words)})
        i=max(i+1,j)
    # Preserve the existing parser's supported dialogue even when attribution is ambiguous.
    represented=Counter(speech_key(v['text']) for v in found)
    fallback_seen=Counter()
    for words in speech_lines(authored_dialogue({'brief':script})):
        key=speech_key(words);fallback_seen[key]+=1
        if fallback_seen[key]<=represented[key]:continue
        found.append({'start':script.find(words),'speaker':None,'language':None,'text':key})
    return sorted(found,key=lambda value:value['start'])
