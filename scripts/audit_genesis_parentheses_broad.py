"""Broad cross-script parentheses inventory: plugin ESM only, no base/DLC Strings."""
import argparse,csv,gzip,hashlib,json,re
from collections import Counter
from pathlib import Path
P=re.compile(r'\(([^()\r\n]{1,130})\)')
E=re.compile('[A-Za-z]');H=re.compile('[가-힣]')
FIELDS=['file','key','pattern','left_context','inside','original_context','source_en']
def scan(repo,out):
    base=repo/'installer-data';manifest=json.loads((base/'manifest.json').read_text(encoding='utf8'))
    counts=Counter();samples=[]
    with out.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,FIELDS);writer.writeheader()
        for op in manifest['operations']:
            if op['kind']!='text_recipe' or op['target'].lower().endswith(('.strings','.dlstrings','.ilstrings')):continue
            b=(base/'blobs'/op['blob']).read_bytes()
            if hashlib.sha256(b).hexdigest()!=op['blob']:raise ValueError('Broken blob')
            recipe=json.loads(gzip.decompress(b))
            if recipe['kind']!='plugin':raise ValueError('Not plugin')
            for key,pair in recipe['translations']:
                en,ko=pair[:2]
                for m in P.finditer(ko):
                    ins=m[1].strip()
                    before=ko[max(0,m.start()-55):m.start()]
                    left=before.strip().split('\n')[-1][-65:]
                    last=left.rstrip()[-1:] if left else ''
                    pattern=('English(Korean)' if H.search(ins) and E.search(last) and not E.search(ins) else
                             'Korean(English)' if E.search(ins) and H.search(last) else None)
                    if not pattern:continue
                    counts[pattern]+=1;counts['total']+=1
                    row={'file':op['target'],'key':json.dumps(key),'pattern':pattern,'left_context':left,
                         'inside':ins,'original_context':ko[max(0,m.start()-70):min(len(ko),m.end()+50)],'source_en':en[:240]}
                    writer.writerow(row)
                    if len(samples)<250:samples.append(row)
    print('BROAD_SUMMARY',json.dumps(dict(counts),ensure_ascii=False))
    print('BROAD_SAMPLES',json.dumps(samples,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path('.'));p.add_argument('--out',type=Path,required=True)
    opts=p.parse_args();scan(opts.repo,opts.out)
