"""Repository-owned, stage-scoped authoring knowledge with immutable request snapshots."""
import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path

ROOT=Path(__file__).resolve().parent/'authoring'
STAGE_FILES={
    'asset_analysis':('common.md','stages/analyse.md'),
    'description_refine':('common.md','stages/refine.md'),
    'prompt_write':('common.md','skills/h3-ref2av/SKILL.md','skills/h3-ref2av/references/ref-en.md','stages/write.md'),
}
_cache={}
_lock=threading.RLock()

@dataclass(frozen=True)
class RuleBundle:
    stage:str
    text:str
    version:str
    files:tuple
    def manifest(self):
        return {'stage':self.stage,'version':self.version,'files':[{'path':name,'sha256':sha} for name,sha in self.files]}

def load_rule_bundle(stage,root=None):
    if stage not in STAGE_FILES:raise ValueError('Unknown authoring-rule stage.')
    root=Path(root) if root is not None else ROOT
    names=STAGE_FILES[stage];key=(str(root.resolve()),stage)
    with _lock:
        try:signature=tuple((name,(s:= (root/name).stat()).st_mtime_ns,s.st_size) for name in names)
        except OSError as error:raise ValueError(f'Missing authoring rule for {stage}: {error.filename}') from error
        prior=_cache.get(key)
        if prior and prior[0]==signature:return prior[1]
        texts=[];files=[]
        for name in names:
            try:raw=(root/name).read_bytes();text=raw.decode('utf-8-sig')
            except (OSError,UnicodeError) as error:raise ValueError(f'Cannot read UTF-8 authoring rule {name}.') from error
            if not text.strip():raise ValueError(f'Authoring rule {name} is empty.')
            texts.append(text.strip());files.append((name,hashlib.sha256(raw).hexdigest()))
        text='\n\n'.join(texts)
        version=hashlib.sha256(json.dumps({'stage':stage,'files':files},ensure_ascii=False).encode()).hexdigest()
        bundle=RuleBundle(stage,text,version,tuple(files));_cache[key]=(signature,bundle)
        return bundle
