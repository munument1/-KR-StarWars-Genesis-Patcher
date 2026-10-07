"""Verify review coverage, final translations and installed recipe alignment."""
import argparse,gzip,hashlib,json,re,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from patch_engine import check_translation
from complete_terminology_review import resolve
from audit_sst_terminology import matcher,save,sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args()
    repo=args.repo;root=repo/'translation-review/terminology-complete';m=json.loads((root/'manifest.json').read_text(encoding='utf-8'));rows=[]
    terms=json.loads((root/'glossary.json').read_text(encoding='utf-8'))['terms'];pattern,aliases=matcher(terms)
    for b in m['batches']:
        path=root/b['file'];assert sha(path)==b['sha256']
        r=json.loads(path.read_text(encoding='utf-8'))['items'];assert len(r)==b['items'];rows+=r
    assert len(rows)==m['sst_findings_reviewed']
    assert Counter(r['review_status'] for r in rows)==m['sst_decisions']
    assert all(r['review_status'] in ('context_validated','context_accepted') for r in rows)
    for r in rows:
        final=r['proposed_ko'] or r['current_ko'];check_translation(r['source_en'],final)
        expected,_=resolve(r['source_en'],r['current_ko'],r['location'],terms,pattern,aliases)
        assert expected==final,'Final review no longer matches reviewed rules'
    original=[r for p in (repo/'translation-review/terminology/sst').glob('*.json') for r in json.loads(p.read_text(encoding='utf-8'))['items']]
    identities={(r['source_en'],r['current_ko'],json.dumps(r['location'],sort_keys=True)) for r in rows}
    assert all((r['source_en'],r['current_ko'],json.dumps(r['location'],sort_keys=True)) in identities for r in original)
    api=[r for p in (repo/'translation-review/terminology-followup').glob('ai-review-*.json') for r in json.loads(p.read_text(encoding='utf-8'))['items']]
    pairs={(r['source_en'],r['current_ko']) for r in rows};assert all((r['source_en'],r['current_ko']) in pairs for r in api)
    manifest=json.loads((repo/'installer-data/manifest.json').read_text(encoding='utf-8'));interaction=[];recipes={}
    for op in manifest['operations']:
        if op['kind']!='text_recipe':continue
        rec=json.loads(gzip.decompress((repo/'installer-data/blobs'/op['blob']).read_bytes()))
        recipes[op['target']]={(tuple(k) if isinstance(k,list) else k):v for k,v in rec['translations']}
        if rec['kind']=='plugin':
            for key,val in rec['translations']:
                if key[2]=='ATTX' and val[0]=='Open':interaction.append(val[1]);assert val[1]=='열기'
    edits=json.loads((root/'recipe-edits.json').read_text(encoding='utf-8'))['items']
    for e in edits:
        loc=e['location'];key=tuple(loc['key']) if isinstance(loc['key'],list) else loc['key']
        assert recipes[loc['target']][key][:2]==[e['source_en'],e['proposed_ko']]
    for p in root.glob('*.json'):
        text=p.read_text(encoding='utf-8');assert not re.search(r'AIza[0-9A-Za-z_-]{30,}',text)
        assert 'C:\\Users\\seung' not in text
    result={'sst_rows_validated':len(rows),'initial_findings_covered':len(original),'api_pairs_finalized':len(api),
            'remaining_review_holds':0,'applied_recipe_edits_verified':len(edits),'open_interaction_labels_verified':len(interaction),
            'public_json_secret_patterns_absent':True}
    save(root/'final-validation.json',result);print(json.dumps(result))

if __name__=='__main__':main()
