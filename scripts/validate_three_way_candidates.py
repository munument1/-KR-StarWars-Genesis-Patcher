"""Validate exported proposals and optionally verify original input hashes."""
import argparse, gzip, hashlib, json
from collections import Counter
from pathlib import Path
from build_three_way_candidates import propose, file_digest

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--review-dir',type=Path,required=True)
    ap.add_argument('--base-data',type=Path)
    ap.add_argument('--audit-dir',type=Path)
    args=ap.parse_args();root=args.review_dir
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    path=root/manifest['comparison_file']
    assert sha(path)==manifest['comparison_sha256'], 'Comparison hash mismatch'
    seen=set();counts=Counter();selected={};total=0
    with gzip.open(path,'rt',encoding='utf-8') as f:
        for line in f:
            row=json.loads(line);key=(row['provider'],row['file'],row['string_id'])
            assert key not in seen, 'Duplicate location';seen.add(key)
            assert row['review_status']=='pending' and row['human_reviewed'] is False
            if row['vanilla_en'] is not None and row['vanilla_ko'] is not None:
                candidate,status,used=propose(row['vanilla_en'],row['vanilla_ko'],row['genesis_en'])
                assert (candidate,status,used)==(row['candidate_ko'],row['reuse_status'],row['term_changes']), 'Proposal mismatch'
            else:assert row['candidate_ko'] is None
            counts[row['reuse_status']]+=1;total+=1
            if row['reuse_status']=='term_swap_candidate' and not row['current_round_excluded']:selected[key]=row
    assert dict(counts)==manifest['reuse_counts']
    batch_seen=set()
    for batch in manifest['review_batches']:
        path=root/batch['file'];assert sha(path)==batch['sha256']
        items=json.loads(path.read_text(encoding='utf-8'))['items'];assert len(items)==batch['items']
        for row in items:
            key=(row['provider'],row['file'],row['string_id'])
            assert key not in batch_seen and selected.get(key)==row;batch_seen.add(key)
    assert batch_seen==set(selected) and len(selected)==manifest['term_review_items']
    checked=0
    for source in manifest['source_provenance']:
        folder=args.audit_dir if source['role'] in ('original_genesis_english_audit','current_round_exclusions') else args.base_data
        if folder is not None:
            assert file_digest(folder/source['file'])==source['sha256'], 'Input changed: '+source['file'];checked+=1
    print(json.dumps({'validated_locations':total,'term_review_items':len(selected),'unchanged_inputs_verified':checked}))

if __name__=='__main__':main()
