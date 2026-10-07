"""Validate editable legacy review data without invoking translation or installation."""
import argparse,hashlib,json,re,sys
from collections import Counter
from pathlib import Path,PurePosixPath
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from patch_engine import check_translation

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify-snapshot',action='store_true');ap.add_argument('--review-dir',type=Path);args=ap.parse_args()
    root=args.review_dir or Path(__file__).resolve().parents[1]/'translation-review/legacy';manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    exclusions=set(json.loads((root/'excluded-source-hashes.json').read_text(encoding='utf-8'))['sha256'])
    seen=set();positions=set();statuses=Counter();total_locations=0
    allowed={'pending','retranslated','qa_passed','context_needed','rejected','approved'}
    for batch in manifest['batches']:
        path=root/batch['path'];raw=path.read_bytes();data=json.loads(raw)
        if args.verify_snapshot and hashlib.sha256(raw).hexdigest()!=batch['sha256']:raise ValueError('Snapshot changed: '+batch['path'])
        if len(data['items'])!=batch['items']:raise ValueError('Batch count changed')
        for r in data['items']:
            source=r['source_en'];current=r['current_patch_ko'];ident=hashlib.sha256(('genesis-legacy-v1\0'+source+'\0'+current).encode()).hexdigest()[:24]
            if r['id']!=ident or ident in seen:raise ValueError('Invalid/duplicate ID')
            seen.add(ident)
            if hashlib.sha256(source.encode()).hexdigest() in exclusions:raise ValueError('Current-round source leaked into legacy data')
            if r['review_status'] not in allowed:raise ValueError('Unknown status')
            if not isinstance(r['human_reviewed'],bool) or not isinstance(r['in_game_verified'],bool):raise ValueError('Invalid verification flags')
            if r['legacy_ko'] not in r['legacy_variants']:raise ValueError('Missing original candidate')
            check_translation(source,current)
            proposed=r['proposed_ko']
            if proposed is not None and not isinstance(proposed,str):raise ValueError('Proposal must be null or text')
            if r['review_status'] in {'qa_passed','approved'}:
                if proposed is None:raise ValueError('Approved without a proposal')
                check_translation(source,proposed)
            for location in r['locations']:
                p=PurePosixPath(location['target'])
                if p.is_absolute() or '..' in p.parts or p.parts[0]!='mods' or ':' in location['target']:raise ValueError('Nonportable target')
                if location['kind']=='plugin':key=(location['target'],location['record'],location['form_id'],location['field'],location['index'])
                else:key=(location['target'],location['string_id'])
                if key in positions:raise ValueError('Duplicate target location')
                positions.add(key);total_locations+=1
            statuses[r['review_status']]+=1
    if len(seen)!=manifest['items'] or total_locations!=manifest['locations']:raise ValueError('Manifest counts differ')
    print(json.dumps({'items':len(seen),'locations':total_locations,'batches':len(manifest['batches']),'statuses':dict(statuses),'excluded_sources':len(exclusions),'snapshot_verified':args.verify_snapshot,'validation':'passed'}))
if __name__=='__main__':main()
