"""Export applied legacy SST translations for future review; never modify patch data."""
import argparse,csv,gzip,hashlib,json,re,sys
from collections import Counter,defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from patch_engine import translation_tokens

def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--audit-dir',type=Path,required=True);ap.add_argument('--batch-size',type=int,default=250);ap.add_argument('--output-dir',type=Path);args=ap.parse_args()
    if args.batch_size<1:raise SystemExit('batch-size must be positive')
    repo=Path(__file__).resolve().parents[1];out=args.output_dir or repo/'translation-review/legacy';batches=out/'batches';batches.mkdir(parents=True,exist_ok=True)
    if list(batches.glob('*.json')):raise SystemExit('Output already exists; preserve review edits and export into a fresh checkout.')
    audit=args.audit_dir;excluded=set();exclusions={}
    for name in ['translation_candidates.csv','semantic_review_suggestions.csv','final_review_suggestions.csv']:
        values={r['source'] for r in read(audit/name)};excluded.update(values);exclusions[name]={'unique_sources':len(values),'sha256':hashlib.sha256((audit/name).read_bytes()).hexdigest()}
    # The same normalization used by the released patch preview; record both old/current values.
    sys.path.insert(0,str(audit.parent));from glossary_rules import normalize
    legacy=defaultdict(list)
    for r in read(audit/'sst_entries.csv'):
        if r['source'] and r['translation'] and r['source']!=r['translation'] and not int(r['flags'])&(2|4|64|128):
            legacy[(r['source'],normalize(r['source'],r['translation']))].append(r)
    context={}
    for r in read(audit/'plugin_entries.csv'):
        context[(r['plugin'].lower(),r['record'],int(r['form_id'],16),r['field'],int(r['index']))]=r.get('edid','')
    suspects={r['source'] for r in read(audit/'terminology_suspects.csv')}
    manifest=json.loads((repo/'installer-data/manifest.json').read_text(encoding='utf-8'));items={};counts=Counter()
    for op in manifest['operations']:
        if op['kind']!='text_recipe':continue
        blob=repo/'installer-data/blobs'/op['blob']
        if not blob.exists():blob=repo/'installer-data/blobs'/(op['blob']+'.bin')
        if not blob.exists():raise SystemExit('Recipe blob missing: '+op['blob'])
        recipe=json.loads(gzip.decompress(blob.read_bytes()))
        for key,pair in recipe['translations']:
            source,current=pair[:2];counts['applied_locations']+=1
            if source in excluded:counts['excluded_current_review_locations']+=1;continue
            matches=legacy.get((source,current))
            if not matches:counts['no_legacy_provenance_locations']+=1;continue
            ident=digest('genesis-legacy-v1\0'+source+'\0'+current)[:24]
            if ident not in items:
                values=sorted({r['translation'] for r in matches});flags=[]
                if source in suspects:flags.append('possible_vanilla_term_leak')
                if any(translation_tokens(source)!=translation_tokens(v) for v in values):flags.append('legacy_placeholder_mismatch')
                if any(source.count('\n')!=v.count('\n') for v in values):flags.append('legacy_newline_mismatch')
                if any('\ufffd' in v for v in [source,*values]):flags.append('replacement_character')
                if not any(re.search('[가-힣]',v) for v in values):flags.append('no_hangul')
                if values!=[current]:flags.append('normalized_in_current_patch')
                refs=[];seen=set()
                for r in matches:
                    ref={k:r[k] for k in ['sst','form_id','record','field','index','group','string_id','flags']}
                    marker=json.dumps(ref,sort_keys=True)
                    if marker not in seen:seen.add(marker);refs.append(ref)
                items[ident]={'id':ident,'source_en':source,'legacy_ko':values[0],'legacy_variants':values,'current_patch_ko':current,'proposed_ko':None,'review_status':'pending','review_flags':flags,'review_notes':'','human_reviewed':False,'in_game_verified':False,'locations':[],'sst_references':refs}
            item=items[ident]
            if item['source_en']!=source or item['current_patch_ko']!=current:raise SystemExit('ID collision')
            loc={'target':op['target'],'kind':recipe['kind']}
            if recipe['kind']=='plugin':
                record,fid,field,index=key;plugin=Path(op['target']).name
                loc.update(plugin=plugin,record=record,form_id=f'{fid:08X}',field=field,index=index,editor_id=context.get((plugin.lower(),record,fid,field,index),''))
            else:loc['string_id']=key
            item['locations'].append(loc);counts['exported_locations']+=1
    rows=sorted(items.values(),key=lambda r:(not bool(r['review_flags']),not any(x.get('field')=='NAM1' or x['target'].lower().endswith('.ilstrings') for x in r['locations']),r['id']))
    files=[]
    for i,start in enumerate(range(0,len(rows),args.batch_size),1):
        chunk=rows[start:start+args.batch_size];name=f'batches/legacy-{i:04d}.json';path=out/name
        save(path,{'schema_version':1,'batch_id':f'legacy-{i:04d}','items':chunk})
        files.append({'path':name,'items':len(chunk),'locations':sum(len(r['locations']) for r in chunk),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    report={'schema_version':1,'created_at':'2026-10-07','target_genesis_version':'8.8.32','legacy_origin':'User-provided SST collection reported as Genesis 8.8.1 translations','scope':'Legacy translations selected by released plugin/Genesis Strings recipes. Current translation/review sources excluded conservatively.','items':len(rows),'locations':counts['exported_locations'],'pending':len(rows),'batch_size':args.batch_size,'batches':files,'counts':dict(counts),'flags':dict(Counter(f for r in rows for f in r['review_flags'])),'current_review_exclusions':exclusions,'original_sst_csv_sha256':hashlib.sha256((audit/'sst_entries.csv').read_bytes()).hexdigest(),'released_manifest_sha256':hashlib.sha256((repo/'installer-data/manifest.json').read_bytes()).hexdigest(),'notes':['Same English with distinct applied Korean stays separate.','Locations use repository-relative mod targets; no local usernames or API keys.','proposed_ko=null means no reviewed replacement yet; data is not applied by the patcher.','Copied vanilla/DLC fallback Strings have no text recipe and are outside this export.']}
    hashes=sorted(digest(source) for source in excluded)
    save(out/'excluded-source-hashes.json',{'schema_version':1,'algorithm':'sha256_utf8_source','count':len(hashes),'sha256':hashes})
    report.update(excluded_unique_sources=len(hashes),exclusion_hashes_file='excluded-source-hashes.json')
    save(out/'manifest.json',report)
    print(json.dumps({k:report[k] for k in ['items','locations','pending','counts','flags']},ensure_ascii=True))
if __name__=='__main__':main()
