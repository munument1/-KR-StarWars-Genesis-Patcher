"""Second pass over archived SST findings; preserve context and never install raw SST guesses."""
import argparse,copy,json,re
from collections import Counter
from pathlib import Path
from audit_sst_terminology import matcher,inspect,proposal,sha,save

EXTRA={
 'Aceles':['아실리스','아셀레스','아셀'], 'Hyperdrive':['중력 구동기','중력구동기','중력 드라이브','그라브 드라이브'],
 'Geonosis':['지오노시','지오노시스'], 'Dantooine':['댄투인'], 'Janese':['자니스'],
 'Scaled Citadel':['스케일드 시타델'], 'Tython':['타이트온','타이돈'],
 'Thrawn':['트론'], 'Grand Admiral':['그랜드 어드미럴'], 'Force Essence':['포스 에센스'], 'Jinan':['진안'],
}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--review-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);args=ap.parse_args()
    if args.output_dir.exists():raise ValueError('Output exists; preserve review edits')
    terms=copy.deepcopy(json.loads((args.review_dir/'glossary.json').read_text(encoding='utf-8'))['terms'])
    for term in terms:
        term['known_variants']=sorted(set(term['known_variants']+EXTRA.get(term['english'],[]))- {term['canonical_ko']},key=len,reverse=True)
    pattern,aliases=matcher(terms);rows=[];counts=Counter()
    manifest=json.loads((args.review_dir/'manifest.json').read_text(encoding='utf-8'))
    for batch in manifest['batches']:
        if not batch['file'].startswith('sst/'):continue
        path=args.review_dir/batch['file'];assert sha(path)==batch['sha256']
        for original in json.loads(path.read_text(encoding='utf-8'))['items']:
            if original['review_status'] not in ('context_needed','partial_rule_validated','structural_hold'):continue
            row=copy.deepcopy(original);source=row['source_en'];ko=row['current_ko']
            hits,issues=inspect(source,ko,pattern,aliases)
            candidate,state=proposal(source,ko,issues,terms,row['location']);accepted=[]
            for issue in issues:
                term=issue['english']
                if term=='Credits' and source.strip().casefold()!='credits' and re.search('돈|보상|급여|수당|대금|요금|지불|값|빚',ko):accepted.append(issue['term_id'])
                elif term=='Galactic Empire' and re.search('제국(?:군| 군대| 관련| 대화|과|이|의|을|에)',ko):accepted.append(issue['term_id'])
                elif term=='Vigilance' and source.startswith(('Vigilance is what keeps','Vigilance protects')) and '경계' in ko:accepted.append(issue['term_id'])
                elif term=='Keth' and "Kres'keth'errylu" in source and '크레스케세릴루' in ko:accepted.append(issue['term_id'])
                elif term=='Jinan' and 'By Jinan' in source and '아이고' in ko:accepted.append(issue['term_id'])
            remaining=inspect(source,candidate or ko,pattern,aliases)[1]
            remaining=[i for i in remaining if i['term_id'] not in accepted]
            technical=(source==ko and (re.search(r'DESIGNER NOTE|\bVFX\b|Misc pointer|\bScene\b',source) or row['location']['record'] in ('BPTD','PROJ','HDPT','SNDR','FLST','SCEN')))
            if technical:candidate=None;state='technical_preserved';remaining=[]
            elif candidate:state='rule_validated' if not remaining else 'partial_rule_validated'
            elif not remaining:state='context_accepted'
            else:state='structural_hold' if original['review_status']=='structural_hold' else 'context_needed'
            row.update(proposed_ko=candidate,review_status=state,remaining_issues=remaining,
                       context_accepted_term_ids=accepted,review_method='second_pass_rules_and_context_filters')
            rows.append(row);counts[state]+=1
    args.output_dir.mkdir(parents=True)
    save(args.output_dir/'glossary-extensions.json',{'terms':terms,'note':'Additional working spelling aliases; context filters do not authorize rewriting unrelated prose.'})
    batches=[]
    for start in range(0,len(rows),250):
        path=args.output_dir/f'recheck-{start//250+1:04}.json';save(path,{'items':rows[start:start+250]})
        batches.append({'file':path.name,'items':len(rows[start:start+250]),'sha256':sha(path)})
    report={'items':len(rows),'unique_source_translation_pairs':len({(r['source_en'],r['current_ko']) for r in rows}),
            'decisions':dict(counts),'batches':batches,'source_manifest_sha256':sha(args.review_dir/'manifest.json'),
            'installer_modified':False,'sst_modified':False,'ai_api_used':False}
    save(args.output_dir/'manifest.json',report);print(json.dumps(report))

if __name__=='__main__':main()
