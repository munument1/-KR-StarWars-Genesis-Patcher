"""Validate every reviewed parenthetical and export proposed translations only.
No plugin payload, manifest or checksum is ever rewritten.
"""
import argparse,contextlib,csv,gzip,hashlib,io,json,tempfile
from collections import defaultdict
from pathlib import Path
import audit_genesis_parentheses_broad as broad
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from patch_engine import check_translation

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo',type=Path,default=Path('.'))
    p.add_argument('--overlay',type=Path,required=True)
    opts=p.parse_args();root=opts.repo
    review=json.loads((root/'translation-review/parentheses/decisions.json').read_text(encoding='utf8'))
    decisions=review['decisions']
    if len(decisions)!=review['counts']['all_candidates']:raise ValueError('Review count mismatch')
    with tempfile.TemporaryDirectory() as temp:
        csvfile=Path(temp)/'broad.csv'
        with contextlib.redirect_stdout(io.StringIO()):
            broad.scan(root,csvfile)
        with csvfile.open('r',encoding='utf-8-sig',newline='') as f:
            actual=list(csv.DictReader(f))
    if len(actual)!=len(decisions):raise ValueError(f'Broad inventory changed: {len(actual)} vs {len(decisions)}')
    accepted=defaultdict(list)
    status={'remove_english':0,'keep':0}
    for i,(old,d) in enumerate(zip(actual,decisions),start=1):
        if (d['id']!=i or d['file']!=old['file'] or d['key']!=json.loads(old['key'])
                or d['inside']!=old['inside'] or d['context']!=old['original_context']):
            raise ValueError(f'Review drift at item {i}: {old["file"]}')
        if d['decision']=='remove_english':
            if not d['before'] or not d['after'] or d['before'] not in d['context']:
                raise ValueError(f'Invalid replacement at item {i}')
            if '('+d['inside']+')' not in d['before']:
                raise ValueError(f'Parenthesized source absent in edit {i}')
            if d['after'] in ('',d['before']):
                raise ValueError(f'Invalid after-value in edit {i}')
            accepted[(d['file'],json.dumps(d['key']))].append(d)
        elif d['decision']!='keep':
            raise ValueError(f'Unknown review decision at item {i}')
        status[d['decision']]+=1
    if status!={'remove_english':14,'keep':171}:raise ValueError('Unexpected review totals: '+str(status))
    manifest=json.loads((root/'installer-data/manifest.json').read_text(encoding='utf8'))
    lookup={r['target']:r for r in manifest['operations'] if r['kind']=='text_recipe'
            and not r['target'].lower().endswith(('.strings','.ilstrings','.dlstrings'))}
    decoded={};results=[]
    for (file,key_str),rules in accepted.items():
        if file not in lookup:raise ValueError('Non-plugin file in review: '+file)
        op=lookup[file];name=op['blob']
        if name not in decoded:
            raw=(root/'installer-data/blobs'/name).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=name:raise ValueError('Blob mismatch: '+name)
            decoded[name]=json.loads(gzip.decompress(raw))['translations']
        keys={json.dumps(k):v for k,v in decoded[name]}
        key=json.loads(key_str)
        if key_str not in keys:raise ValueError('Missing key in plugin recipe: '+key_str)
        pair=keys[key_str];source,current=pair[:2]
        revised=current
        for d in rules:
            if revised.count(d['before'])!=1:raise ValueError('Missing or duplicate span at review '+str(d['id']))
            revised=revised.replace(d['before'],d['after'],1)
        # The underlying patcher itself requires exact placeholders and newline retention.
        check_translation(source,revised)
        if revised==current:raise ValueError('No content changed at '+key_str)
        if source.count('\n')!=revised.count('\n') or source.count('\r')!=revised.count('\r'):
            raise ValueError('Line break drift')
        results.append({'target':file,'key':key,'source_en':source,'current_ko':current,'proposed_ko':revised,
                        'approved_occurrences':[d['id'] for d in rules],
                        'human_reviewed':False,'in_game_verified':False})
    output={'schema':1,'scope':'plugin recipes only (NO base or DLC Strings)',
            'reviewed_candidates':len(decisions),'remove_english_occurrences':status['remove_english'],
            'kept_occurrences':status['keep'],'translation_records_to_update':len(results),
            'status':'reviewed overlay only; NOT installed, checksums NOT recomputed',
            'proposals':results}
    opts.overlay.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('REVIEW_VALIDATION',json.dumps({k:v for k,v in output.items() if k!='proposals'},ensure_ascii=False))
    for result in results:
        ids=result['approved_occurrences']
        print('PROPOSAL',json.dumps({'file':result['target'],'key':result['key'],'ids':ids,
              'before':result['current_ko'][:150],'after':result['proposed_ko'][:150]},ensure_ascii=False))
if __name__=='__main__':
    main()
