"""Losslessly update reviewed SST translations with snapshots and rollback."""
import argparse,json,struct,subprocess,sys,uuid
from collections import Counter,defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from installer_backend import atomic,sha,safe,save
from patch_engine import check_translation

def ensure_translator_closed():
    if sys.platform=='win32':
        result=subprocess.run(['tasklist','/FI','IMAGENAME eq xTranslator.exe','/FO','CSV','/NH'],capture_output=True,check=True)
        if b'xtranslator.exe' in result.stdout.lower():
            raise ValueError('Save your work and close xTranslator before applying SST changes')

def parse(data):
    pos=0
    def take(n):
        nonlocal pos
        if n<0 or pos+n>len(data):raise ValueError('Invalid SST bounds')
        raw=data[pos:pos+n];pos+=n;return raw
    def number(fmt):return struct.unpack(fmt,take(struct.calcsize(fmt)))[0]
    def string():
        size=number('<i')
        if size%2:raise ValueError('Invalid UTF16 size')
        return take(size).decode('utf-16-le')
    header=take(4)
    if header[:3]!=b'SSU' or not 50<=header[3]<=57:raise ValueError('Unknown SST format')
    version=header[3]-49
    if version>3:take(1)
    if version>7:
        for _ in range(number('<i')):string()
    if version>6:
        for _ in range(number('<i')):take(4);string()
    prefix=data[:pos];rows=[]
    while pos<len(data):
        start=pos;group=number('<B');sid=fid=index=0;record=field=''
        if version>1:
            sid=number('<I');fid=number('<I')
            if version>4:record=take(4).decode('ascii')
            field=take(4).decode('ascii')
            if version>2:index=number('<H')
            if version>3:take(2);take(4)
            if version>5:take(1)
        flags=number('<B');source=string();translation_start=pos;translation=string()
        if group>2:raise ValueError('Invalid SST list')
        rows.append({'key':(str(group),str(sid),f'{fid:08X}',record,field,str(index)),
                     'source':source,'translation':translation,'flags':flags,
                     'translation_span':(translation_start,pos),'metadata':data[start:translation_start]})
    return prefix,rows

def patch(data,edits):
    prefix,rows=parse(data);spans=[];used=Counter()
    for row in rows:
        edit=edits.get(row['key'])
        if edit is None or row['flags']&(2|4|64|128):continue
        old,new,source=edit
        if (row['source'],row['translation'])!=(source,old):raise ValueError('SST entry changed since review')
        check_translation(source,new);encoded=new.encode('utf-16-le')
        spans.append((*row['translation_span'],struct.pack('<i',len(encoded))+encoded));used[row['key']]+=1
    if set(used)!=set(edits) or any(n!=1 for n in used.values()):raise ValueError('Missing or duplicate reviewed SST location')
    result=data
    for start,end,value in reversed(spans):result=result[:start]+value+result[end:]
    newprefix,newrows=parse(result)
    if newprefix!=prefix or len(newrows)!=len(rows):raise ValueError('SST header/count changed')
    for before,after in zip(rows,newrows):
        if before['metadata']!=after['metadata']:raise ValueError('SST source/flags/record metadata changed')
        expected=edits[before['key']][1] if before['key'] in edits and not before['flags']&(2|4|64|128) else before['translation']
        if after['translation']!=expected:raise ValueError('Unexpected SST translation change')
    return result,len(spans)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--sst-dir',type=Path,required=True)
    ap.add_argument('--stage',type=Path,required=True);ap.add_argument('--apply',action='store_true')
    ap.add_argument('--review-dir',type=Path);ap.add_argument('--snapshot',type=Path);args=ap.parse_args()
    if args.stage.exists():raise ValueError('Preserve previous stage')
    if args.stage.resolve().is_relative_to(args.sst_dir.resolve()):raise ValueError('Stage must be outside dictionaries')
    review=args.review_dir or args.repo/'translation-review/terminology-complete';m=json.loads((review/'manifest.json').read_text(encoding='utf-8'));edits=defaultdict(dict)
    for batch in m['batches']:
        path=review/batch['file']
        if sha(path.read_bytes())!=batch['sha256']:raise ValueError('Review batch changed')
        for r in json.loads(path.read_text(encoding='utf-8'))['items']:
            if r['proposed_ko'] is None:continue
            loc=r['location'];key=tuple(str(loc[k]) for k in ('group','string_id','form_id','record','field','index'))
            if key in edits[loc['sst']]:raise ValueError('Duplicate review location')
            edits[loc['sst']][key]=(r['current_ko'],r['proposed_ko'],r['source_en'])
    snapshot=json.loads((args.snapshot or args.repo/'translation-review/terminology/source-verification.json').read_text(encoding='utf-8'))['files']
    for f in snapshot:
        if sha(safe(args.sst_dir,f['sst']).read_bytes())!=f['sha256']:raise ValueError('SST changed since verified snapshot: '+f['sst'])
    args.stage.mkdir(parents=True);entries=[]
    for name,changes in edits.items():
        source=safe(args.sst_dir,name);raw=source.read_bytes();output,count=patch(raw,changes)
        atomic(safe(args.stage/'originals',name),raw);atomic(safe(args.stage/'updated',name),output)
        entries.append({'sst':name,'input_sha256':sha(raw),'output_sha256':sha(output),'changed_translations':count})
    report={'state':'prepared','files':len(entries),'changed_translations':sum(e['changed_translations'] for e in entries),'all_source_and_metadata_preserved':True,'entries':entries}
    save(args.stage/'report.json',report)
    if args.apply:
        ensure_translator_closed()
        for e in entries:
            if sha(safe(args.sst_dir,e['sst']).read_bytes())!=e['input_sha256']:raise ValueError('SST changed after staging')
        backup=args.sst_dir/'.genesis-kr-sst-backups'/uuid.uuid4().hex;backup.mkdir(parents=True)
        for e in entries:atomic(safe(backup/'originals',e['sst']),safe(args.stage/'originals',e['sst']).read_bytes())
        save(backup/'journal.json',report)
        applied=[]
        try:
            ensure_translator_closed()
            for e in entries:
                target=safe(args.sst_dir,e['sst'])
                if sha(target.read_bytes())!=e['input_sha256']:raise ValueError('SST changed while applying')
                atomic(target,safe(args.stage/'updated',e['sst']).read_bytes());applied.append(e)
            for e in entries:
                if sha(safe(args.sst_dir,e['sst']).read_bytes())!=e['output_sha256']:raise ValueError('Written SST checksum mismatch')
        except Exception:
            for e in reversed(applied):atomic(safe(args.sst_dir,e['sst']),safe(backup/'originals',e['sst']).read_bytes())
            raise
        report.update(state='applied',backup=str(backup));save(args.stage/'report.json',report);save(backup/'journal.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='entries'}))

if __name__=='__main__':main()
