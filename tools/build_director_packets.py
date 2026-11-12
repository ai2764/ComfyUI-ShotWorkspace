"""Maintainer-only build/check; never run by imported skills or LLM requests."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'authoring/skills/director-style'


def packet(shared, profile):
    return '# Director planning packet — v2.2.4\n\n'+shared+'\n\n## Selected creative direction\n\n'+profile


def main():
    shared=(ROOT/'references/shared.md').read_text(encoding='utf8')
    (ROOT/'injection').mkdir(exist_ok=True)
    failed=[]
    for path in (ROOT/'profiles').glob('*.md'):
        content=packet(shared,path.read_text(encoding='utf8'))
        target=ROOT/'injection'/path.name
        if '--check' in sys.argv:
            if not target.exists() or target.read_text(encoding='utf8')!=content:failed.append(path.name)
        else:target.write_text(content,encoding='utf8')
    if failed:raise SystemExit('Stale director packets: '+', '.join(failed))


if __name__=='__main__':main()
