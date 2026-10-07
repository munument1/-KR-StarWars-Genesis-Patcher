"""Export terminology-only AI drafts with independent checks, never install them."""
import argparse,csv,json,re
from collections import Counter
from pathlib import Path
from audit_sst_terminology import inspect,matcher,save,sha
from patch_engine import check_translation

def within_scope(previous,proposed,terms):
    names={name:t['id'] for t in terms for name in [t['canonical_ko'],*t['known_variants']] if name}
    if not names:return previous==proposed
    pattern=re.compile('|'.join(re.escape(n) for n in sorted(names,key=len,reverse=True)))
    def mask(text):
        return pattern.sub(lambda m:'{TERM:'+names[m[0]]+'}',text)
    before,after=mask(previous),mask(proposed)
    # Inflection changes immediately after a masked name are permitted. Other
    # edits remain held, even when the model claims they are terminology edits.
    particle=re.compile(r'(\{TERM:[a-f0-9]+\})(?:으로|로|은|는|이|가|을|를|과|와)(?=$|[^가-힣]|(?:부터|는|다|랑|라고|라는|었던))')
    before=particle.sub(r'\1{PARTICLE}',before)
    after=particle.sub(r'\1{PARTICLE}',after)
    return before==after

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--raw',type=Path,nargs='+',required=True)
    ap.add_argument('--review-dir',type=Path,required=True);args=ap.parse_args()
    terms=json.loads((args.review_dir/'glossary-extensions.json').read_text(encoding='utf-8'))['terms']
    pattern,aliases=matcher(terms)
    with args.input.open(encoding='utf-8-sig',newline='') as f:inputs={r['id']:r for r in csv.DictReader(f)}
    raw={}
    for path in args.raw:
        for line in path.read_text(encoding='utf-8').splitlines():
            r=json.loads(line);raw[r['id']]=r
    if set(raw)!=set(inputs):raise ValueError('Missing or unexpected AI results')
    rows=[];counts=Counter()
    for key,item in inputs.items():
        draft=raw[key];source=item['source'];old=item['translation'];new=draft['translation']
        if draft['source']!=source or draft['previous_translation']!=old:raise ValueError('Source mismatch')
        structure_error=None
        try:check_translation(source,new)
        except ValueError as e:structure_error=str(e)
        # Names contained only in engine aliases are tokens, not displayed prose.
        visible_source=re.sub(r'<[^>]*>','',source)
        hits,issues=inspect(visible_source,new,pattern,aliases)
        relevant=[t for t in terms if t['id'] in hits]
        scope=within_scope(old,new,relevant)
        technical=old==source and new==source and not re.search('[가-힣]',new)
        context_accepted=[]
        for issue in issues:
            if issue['english']=='Credits' and source.strip().lower()!='credits' and re.search('돈|보상|급여|수당|대금|요금|지불|값|빚',new):context_accepted.append(issue['term_id'])
            elif issue['english']=='Galactic Empire' and '제국' in new:context_accepted.append(issue['term_id'])
            elif issue['english']=='Keth' and "Kres'keth'errylu" in source and '크레스케세릴루' in new:context_accepted.append(issue['term_id'])
        remaining=[i for i in issues if i['term_id'] not in context_accepted]
        if structure_error:state='structural_hold'
        elif draft['decision']=='context_needed':state='context_needed'
        elif not scope:state='scope_hold'
        elif technical:state='technical_preserved'
        elif remaining:state='terminology_hold'
        elif new==old:state='context_accepted'
        else:state='ai_suggestion_validated'
        rows.append({'id':key,'source_en':source,'current_ko':old,'proposed_ko':new if new!=old else None,
                     'locations':json.loads(item['locations']),'review_status':state,
                     'model':draft['model'],'model_decision':draft['decision'],'model_note':draft['review_note'],
                     'structural_error':structure_error,'terminology_only_scope_passed':scope,
                     'remaining_issues':remaining,'human_reviewed':False,'installer_applied':False})
        counts[state]+=1
    batches=[]
    for start in range(0,len(rows),250):
        path=args.review_dir/f'ai-review-{start//250+1:04}.json';save(path,{'items':rows[start:start+250]})
        batches.append({'file':path.name,'items':len(rows[start:start+250]),'sha256':sha(path)})
    report={'unique_pairs':len(rows),'locations':sum(len(r['locations']) for r in rows),'decisions':dict(counts),
            'batches':batches,'input_sha256':sha(args.input),'glossary_sha256':sha(args.review_dir/'glossary-extensions.json'),
            'ai_api_used':True,'models':sorted({r['model'] for r in rows}),
            'installer_modified':False,'sst_modified':False,'human_reviewed':False}
    save(args.review_dir/'ai-manifest.json',report);print(json.dumps(report))

if __name__=='__main__':main()
