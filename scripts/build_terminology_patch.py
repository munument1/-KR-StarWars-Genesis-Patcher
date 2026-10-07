"""Integrate verified plugin terminology proposals into a separate installer package."""
import argparse,gzip,hashlib,json,shutil,sys
from collections import Counter,defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from patch_engine import patch_plugin,check_translation
from installer_backend import safe

def sha(raw):return hashlib.sha256(raw).hexdigest()
def mapping(recipe):return {tuple(k):tuple(v) for k,v in recipe['translations']}
def blob(package,values):
    raw=gzip.compress(json.dumps({'kind':'plugin','translations':sorted(values.items())},ensure_ascii=False,separators=(',',':')).encode(),mtime=0)
    digest=sha(raw);(package/'blobs'/digest).write_bytes(raw);return digest
def compose(first,second):
    result=dict(first)
    for key,value in second.items():
        if key in first:
            previous=first[key]
            if previous[1]!=value[0]:raise ValueError('Upgrade composition mismatch')
            result[key]=(previous[0],value[1])+previous[2:]
        else:result[key]=value
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--game',type=Path,required=True);ap.add_argument('--package',type=Path,required=True)
    ap.add_argument('--review-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);args=ap.parse_args()
    for protected in (args.game,args.package,args.review_dir):
        if args.output_dir.resolve().is_relative_to(protected.resolve()) or protected.resolve().is_relative_to(args.output_dir.resolve()):raise ValueError('Build must be outside inputs')
    if args.output_dir.exists():raise ValueError('Output already exists')
    audit=json.loads((args.review_dir/'manifest.json').read_text(encoding='utf-8'));selected=defaultdict(dict);dispositions=Counter()
    for batch in audit['batches']:
        if not batch['file'].startswith('plugin/'):continue
        path=safe(args.review_dir,batch['file']);assert sha(path.read_bytes())==batch['sha256']
        for item in json.loads(path.read_text(encoding='utf-8'))['items']:
            dispositions[item['review_status']]+=1
            if item['review_status'] not in ('rule_validated','context_validated','context_validated_provisional_name'):continue
            loc=item['location'];key=(loc['record'],int(loc['form_id'],16),loc['field'],loc['index'])
            check_translation(item['source_en'],item['proposed_ko'])
            if key in selected[loc['target']]:raise ValueError('Duplicate target')
            selected[loc['target']][key]=item
    manifest=json.loads((args.package/'manifest.json').read_text(encoding='utf-8'))
    args.output_dir.mkdir(parents=True);output=args.output_dir/'installer-data';shutil.copytree(args.package,output)
    backups=list((args.game/'.genesis-kr-backups').glob('*/originals'));operations=[];results=[];seen=set()
    for original_op in manifest['operations']:
        op=dict(original_op);edits=selected.get(op['target'])
        if not edits:operations.append(op);continue
        seen.add(op['target']);recipe=json.loads(gzip.decompress(safe(args.package,'blobs/'+op['blob']).read_bytes()))
        if recipe['kind']!='plugin':raise ValueError('Review target is not plugin')
        old=mapping(recipe);new=dict(old);upgrade={}
        for key,item in edits.items():
            if key not in old or old[key][:2]!=(item['source_en'],item['current_ko']):raise ValueError('Recipe changed since review')
            new[key]=(old[key][0],item['proposed_ko'])+old[key][2:]
            if old[key][1]!=new[key][1]:upgrade[key]=(old[key][1],new[key][1])
        source=None
        for root in backups+[args.game]:
            path=safe(root,op['target'])
            if path.is_file():
                raw=path.read_bytes()
                if sha(raw)==op['input_sha256']:source=raw;break
        if source is None:raise ValueError('Original plugin missing: '+op['target'])
        before,_=patch_plugin(source,old)
        if sha(before)!=op['output_sha256']:raise ValueError('Existing recipe hash mismatch')
        after,changed=patch_plugin(source,new)
        upgraded,_=patch_plugin(before,upgrade)
        if after!=upgraded:raise ValueError('Upgrade differs from clean output')
        upgrades=[]
        for previous in op.get('upgrade_from',[]):
            prior=json.loads(gzip.decompress(safe(args.package,'blobs/'+previous['blob']).read_bytes()))
            upgrades.append({'input_sha256':previous['input_sha256'],'blob':blob(output,compose(mapping(prior),upgrade))})
        upgrades.append({'input_sha256':sha(before),'blob':blob(output,upgrade)})
        op.update(blob=blob(output,new),output_sha256=sha(after),text_changes=len(changed),upgrade_from=upgrades)
        staged=safe(args.output_dir/'preview',op['target']);staged.parent.mkdir(parents=True,exist_ok=True);staged.write_bytes(after)
        results.append({'target':op['target'],'changed_locations':len(upgrade),'output_sha256':sha(after)})
        operations.append(op)
    if seen!=set(selected):raise ValueError('Review targets absent from package')
    report={'schema_version':1,'review_manifest_sha256':sha((args.review_dir/'manifest.json').read_bytes()),
            'glossary_sha256':sha((args.review_dir/'glossary.json').read_bytes()),'dispositions':dict(dispositions),
            'changed_locations':sum(r['changed_locations'] for r in results),'changed_plugin_files':len(results),
            'results':results,'clean_and_upgrade_outputs_identical':True,'game_modified':False}
    manifest.update(operations=operations,release_state='TEST_BUILD',in_game_verified=False,terminology_revision=report)
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (args.output_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}))

if __name__=='__main__':main()
