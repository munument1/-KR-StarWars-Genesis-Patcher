import argparse,json
from collections import Counter
from pathlib import Path
from audit_sst_terminology import sha,glossary,matcher,inspect,proposal,reviewed_context

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--review-dir',type=Path,required=True);ap.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);args=ap.parse_args()
    root=args.review_dir;m=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    terms=json.loads((root/'glossary.json').read_text(encoding='utf-8'))['terms'];ids={t['id'] for t in terms}
    assert len(terms)==len(ids)==m['glossary_terms']
    current=glossary(args.repo/'translation-review/GLOSSARY.md')
    assert [(t['id'],t['canonical_ko'],t['known_variants']) for t in current]==[(t['id'],t['canonical_ko'],t['known_variants']) for t in terms]
    pattern,aliases=matcher(terms);counts=Counter();seen=set()
    for batch in m['batches']:
        path=root/batch['file'];assert sha(path)==batch['sha256']
        items=json.loads(path.read_text(encoding='utf-8'))['items'];assert len(items)==batch['items']
        scope=Path(batch['file']).parts[0]
        for item in items:
            key=(scope,json.dumps(item['location'],sort_keys=True));assert key not in seen;seen.add(key)
            assert all(i['term_id'] in ids for i in item['issues']) and item['human_reviewed'] is False
            assert inspect(item['source_en'],item['current_ko'],pattern,aliases)[1]==item['issues']
            value,state=proposal(item['source_en'],item['current_ko'],item['issues'],terms,item['location'])
            cv,cs=reviewed_context(item['source_en'],item['current_ko'])
            if cs:value,state=cv,cs
            remaining=inspect(item['source_en'],value,pattern,aliases)[1] if value else item['issues']
            if cs:remaining=[]
            elif value and remaining:state='partial_rule_validated'
            assert (value,state,remaining)==(item['proposed_ko'],item['review_status'],item['remaining_issues'])
            counts[scope+'_'+state]+=1
    assert dict(counts)==m['review_decisions']
    assert sum(v for k,v in counts.items() if k.startswith('plugin_'))==m['current_plugin_findings']
    assert sum(v for k,v in counts.items() if k.startswith('sst_'))==m['sst_findings']
    verification=root/m['source_verification']['file'];assert sha(verification)==m['source_verification']['sha256']
    sources=json.loads(verification.read_text(encoding='utf-8'))
    assert len(sources['files'])==m['sst_files'] and sum(r['rows'] for r in sources['files'])==m['sst_rows']
    assert m['eligible_sst_rows']+sum(m['excluded_sst_rows'].values())==m['sst_rows']
    print(json.dumps({'validated_glossary_terms':len(terms),'validated_findings':len(seen),'decisions':dict(counts)}))

if __name__=='__main__':main()
