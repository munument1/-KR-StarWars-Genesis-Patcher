"""Read-only review of bilingual parentheses in Genesis plugin translations.
Base-game and DLC .strings/.dlstrings/.ilstrings are EXCLUDED by default.
Usage: python scripts/audit_genesis_parentheses.py --repo . --out audit.csv --summary-json summary.json
"""
import argparse,csv,gzip,hashlib,json,re
from collections import Counter,defaultdict
from pathlib import Path

H=re.compile('[가-힣]'); E=re.compile('[A-Za-z]')
P=re.compile(r'\(([^()\r\n]{1,110})\)')
K=re.compile(r"([가-힣][가-힣·'’-]*(?:\s+[가-힣][가-힣·'’-]*){0,6})\s*$")
N=re.compile(r"([A-Za-z][A-Za-z0-9'’./-]*(?:\s+[A-Za-z][A-Za-z0-9'’./-]*){0,5})\s*$")
C=re.compile(r'(?:[A-Z]{1,7}[-_]?\d+[A-Za-z0-9/-]*|[A-Z]{2,8})')
EX={'요약','설명','참고','주의','버그 신고','작업 중','출시 예정','구','신','씨앗','동체','가죽','줄기','분비선','소형 포트','완전 자동 조종 시스템'}
STRINGS=('.strings','.dlstrings','.ilstrings')
FIELDS=('file','key','direction','left_context','parenthetical','source_en','current_ko','proposed_ko','note')

def candidates(ko,en):
    for match in P.finditer(ko):
        inside=match[1].strip()
        before=ko[max(0,match.start()-100):match.start()]
        if not before or any(c in inside for c in '<>{}\\'):
            continue
        if H.search(inside) and not E.search(inside):
            m=N.search(before)
            if not m or C.fullmatch(m[1].strip()) or inside in EX:continue
            left=m[1].strip()
            if left.casefold() not in en.casefold():continue
            start=match.start()-(len(before)-m.start(1))
            suggestion=ko[:start]+inside+ko[match.end():]
            direction='English(Korean)'
        elif E.search(inside) and not H.search(inside):
            m=K.search(before)
            if not m or C.fullmatch(inside) or len(inside)<2:continue
            if re.search(r'[/=<>%{}\[\]0-9]',inside):continue
            if inside.casefold() not in en.casefold():continue
            left=m[1].strip()
            suggestion=ko[:match.start()]+ko[match.end():]
            direction='Korean(English)'
        else:continue
        if suggestion!=ko:
            yield {'direction':direction,'left_context':left,'parenthetical':inside,'proposed_ko':suggestion,
                   'note':'Candidate ONLY. Verify same-name bilingual duplication; keep explanatory parentheses.'}

def scan(repo,out,summary_path):
    base=repo/'installer-data'
    manifest=json.loads((base/'manifest.json').read_text(encoding='utf8'))
    counts=Counter();examples=[];byfile=Counter()
    with out.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,FIELDS);writer.writeheader()
        for op in manifest['operations']:
            if op['kind']!='text_recipe':
                counts['non_translation_operations_excluded']+=1;continue
            if op['target'].lower().endswith(STRINGS):
                counts['base_dlc_strings_excluded']+=1;continue
            counts['plugin_operations']+=1
            raw=(base/'blobs'/op['blob']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=op['blob']:
                raise ValueError('Package blob checksum mismatch: '+op['target'])
            recipe=json.loads(gzip.decompress(raw))
            if recipe['kind']!='plugin':raise ValueError('Unexpected plugin recipe: '+op['target'])
            for key,pair in recipe['translations']:
                if len(pair)<2:continue
                counts['plugin_translation_rows']+=1
                src,translation=pair[:2]
                for c in candidates(translation,src):
                    counts['candidate_occurrences']+=1
                    counts[c['direction']]+=1;byfile[op['target']]+=1
                    row={'file':op['target'],'key':json.dumps(key,ensure_ascii=False),
                         'source_en':src,'current_ko':translation,**c}
                    writer.writerow(row)
                    if len(examples)<80: examples.append(row)
    result={'scope':'PLUGIN ONLY (base-game + DLC .strings/.dlstrings/.ilstrings excluded)',
            'counts':dict(counts),'candidates_by_plugin':dict(byfile),
            'sample_candidates':examples,'actual_text_changes':0,
            'base_strings_unchanged':True}
    summary_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('AUDIT_SUMMARY',json.dumps({k:v for k,v in result.items() if k!='sample_candidates'},ensure_ascii=False))
    print('REVIEW_SAMPLES',json.dumps(examples[:60],ensure_ascii=False))

def test():
    cases=[('헤이드리안(Hadrian)','Hadrian','헤이드리안'),
           ('Dantooine(단투인)','Dantooine','단투인'),
           ('단투인(Dantooine)','Dantooine','단투인'),
           ('Darth Vader(다스 베이더)에게','Darth Vader','다스 베이더에게'),
           ('번역(요약)','Translation',None),
           ('CAPS(완전 자동 조종 시스템)','CAPS',None),
           ('A-280 (버그 신고)','A-280 (report this as a bug)',None),
           ('은하 뉴스 네트워크(GNN)','Galactic News Network (GNN)',None),
           ('X-윙 (S) 원자로 (C)','X-wing (S) Reactor (C)',None),
           ('우주 너머 (<Alias=Planet>)','From Beyond (<Alias=Planet>)',None)]
    for ko,en,expected in cases:
        found=list(candidates(ko,en))
        got=found[0]['proposed_ko'] if found else None
        assert got==expected,(ko,expected,got)
    print('PASS',len(cases),'tests')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo',type=Path,default=Path('.'))
    p.add_argument('--out',type=Path)
    p.add_argument('--summary-json',type=Path)
    p.add_argument('--self-test',action='store_true')
    args=p.parse_args()
    if args.self_test:test();return
    if not args.out or not args.summary_json:p.error('--out and --summary-json are required')
    scan(args.repo,args.out,args.summary_json)
if __name__=='__main__':main()
