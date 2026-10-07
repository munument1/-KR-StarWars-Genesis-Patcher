"""Prioritize Genesis-changed Strings using a read-only vanilla archive comparison."""
import argparse,hashlib,json,struct,sys,zlib
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from patch_engine import read_strings

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base-data',type=Path,required=True);ap.add_argument('--review-dir',type=Path);args=ap.parse_args()
    root=args.review_dir or Path(__file__).resolve().parents[1]/'translation-review/legacy';mp=root/'manifest.json';manifest=json.loads(mp.read_text(encoding='utf-8'));base={};archives=[]
    for archive in sorted(args.base_data.glob('*Localization.ba2')):
        with archive.open('rb') as f:
            header=f.read(32);magic,version,kind,count,offset=struct.unpack_from('<4sI4sIQ',header)
            if magic!=b'BTDX' or kind!=b'GNRL' or version!=2:raise SystemExit('Unsupported archive: '+archive.name)
            f.seek(offset);names=[f.read(struct.unpack('<H',f.read(2))[0]).decode('utf-8') for _ in range(count)]
            found=[]
            for index,name in enumerate(names):
                filename=Path(name.replace('\\','/')).name.lower()
                if '_en.' not in filename or Path(filename).suffix not in ('.strings','.dlstrings','.ilstrings'):continue
                f.seek(32+index*36);rec=struct.unpack('<I4sIIQIII',f.read(36));f.seek(rec[4]);raw=f.read(rec[5] or rec[6]);raw=zlib.decompress(raw) if rec[5] else raw
                if len(raw)!=rec[6]:raise SystemExit('Archive size mismatch')
                base[filename]={sid:text for sid,text,_ in read_strings(raw,Path(filename).suffix)};found.append(filename)
            archives.append({'archive':archive.name,'english_strings_files':found})
    if not base:raise SystemExit('No vanilla English Strings found')
    rows=[];scopes=Counter()
    for batch in manifest['batches']:
        data=json.loads((root/batch['path']).read_text(encoding='utf-8'))
        for item in data['items']:
            if item['proposed_ko'] is not None or item['review_status']!='pending':raise SystemExit('Existing review edits detected; classification cannot reorder them.')
            flags=set()
            for location in item['locations']:
                if location['kind']=='plugin':scope='plugin_text'
                else:
                    filename=Path(location['target']).name.lower();vanilla=base.get(filename,{}).get(location['string_id'])
                    scope='no_base_reference' if vanilla is None else 'genesis_changed_strings' if vanilla!=item['source_en'] else 'vanilla_unchanged_strings'
                    if scope=='genesis_changed_strings':location['vanilla_source_en']=vanilla
                location['source_scope']=scope;flags.add(scope)
            item['source_scope']=sorted(flags)
            item['priority']=0 if item['review_flags'] else 1 if 'genesis_changed_strings' in flags or 'plugin_text' in flags else 2 if 'no_base_reference' in flags else 3
            for flag in flags:scopes[flag]+=1
            rows.append(item)
    rows.sort(key=lambda r:(r['priority'],r['id']))
    for index,batch in enumerate(manifest['batches']):
        chunk=rows[index*manifest['batch_size']:(index+1)*manifest['batch_size']];path=root/batch['path']
        data={'schema_version':1,'batch_id':path.stem,'items':chunk};path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        batch.update(items=len(chunk),locations=sum(len(r['locations']) for r in chunk),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),priorities=dict(Counter(r['priority'] for r in chunk)))
    manifest['source_scope_counts']=dict(scopes);manifest['priority_counts']=dict(Counter(r['priority'] for r in rows));manifest['vanilla_reference_archives']=archives
    manifest['notes'].append('Vanilla English is comparison context only; source_en remains the Genesis translation source. Unknown scope is not evidence of changed vanilla text.')
    mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'items':len(rows),'scope_counts':dict(scopes),'priorities':manifest['priority_counts']}))
if __name__=='__main__':main()
