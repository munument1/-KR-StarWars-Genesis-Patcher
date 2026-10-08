"""Read-only audit of complete installed text, including unpatched fields."""
import argparse,ast,csv,html,json,re,struct,sys,unicodedata,zlib
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from patch_engine import field_spans,read_strings
from apply_reviewed_sst import parse

BRACKETS=re.compile(r'\(([^()]*)\)|（([^（）]*)）|\[([^\[\]]*)\]|【([^【】]*)】|〔([^〔〕]*)〕')
CAPTION=re.compile(r'\bcaption\s*=\s*([\"\'])(.*?)\1',re.S|re.I)
def latin(text):return any('LATIN' in unicodedata.name(c,'') for c in text)
def korean(text):return bool(re.search('[가-힣ㄱ-ㅎㅏ-ㅣ]',text))
def inspect(text,location):
    captions=[]
    def strip(m):
        caption=CAPTION.search(m[0])
        if caption:captions.append(caption[2])
        return ''
    display=html.unescape(re.sub(r'<[^>]*>',strip,text));result=[]
    for section,value in [('body',display)]+[('image_caption',v) for v in captions]:
        for m in BRACKETS.finditer(value):
            inner=next(v for v in m.groups() if v is not None);left=value[max(0,m.start()-65):m.start()]
            if not ((latin(inner) and korean(left)) or (korean(inner) and latin(left))):continue
            result.append(dict(text=text,location=location,section=section,bracket=m[0],inner=inner,
                               context=left+m[0]+value[m.end():m.end()+25]))
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--audit',type=Path,required=True)
    ap.add_argument('--game',type=Path,required=True);ap.add_argument('--sst-dir',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);found=[];counts=Counter()
    rules=[]
    for line in Path(r'F:\번역\프로그램\xTranslator\Data\Starfield\_recorddefs.txt').read_text(encoding='utf-8-sig').splitlines():
        m=re.match(r'Def_:(....)=(....)=([012])(.*)',line)
        if m:field,record,group,extra=m.groups();rules.append((field,record,int(group),extra))
    fn=next(n for n in ast.parse((args.audit/'plugin_audit.py').read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='allowed')
    ns={'rules':rules};exec(compile(ast.Module(body=[fn],type_ignores=[]),'record-definition-filter','exec'),ns)
    plugins=list(csv.DictReader((args.audit/'output/plugins.csv').open(encoding='utf-8-sig')))
    for entry in plugins:
        path=Path(entry['path']).resolve()
        if not path.is_relative_to(args.game.resolve()):raise ValueError('Plugin outside Game')
        raw=path.read_bytes();localized=False;target=path.relative_to(args.game.resolve()).as_posix();counts['installed_plugins']+=1
        def walk(start,end):
            nonlocal localized
            pos=start
            while pos<end:
                if pos+24>end:raise ValueError('Truncated record')
                record=raw[pos:pos+4].decode('ascii');size=struct.unpack_from('<I',raw,pos+4)[0]
                if record=='GRUP':
                    if size<24 or pos+size>end:raise ValueError('Invalid group')
                    walk(pos+24,pos+size);pos+=size;continue
                flags,fid=struct.unpack_from('<II',raw,pos+8);finish=pos+24+size
                if finish>end:raise ValueError('Invalid record length')
                body=raw[pos+24:finish];pos=finish
                if record=='TES4':localized=bool(flags&0x80)
                if flags&0x20:continue
                if flags&0x40000:
                    length=struct.unpack_from('<I',body)[0];body=zlib.decompress(body[4:]);assert len(body)==length
                fields=list(field_spans(body));sub=[(n,v) for n,_,v,_ in fields]
                edid=next((v.rstrip(b'\0').decode('utf-8',errors='replace') for n,v in sub if n=='EDID'),'')
                for i,(field,index,value,_) in enumerate(fields):
                    if localized or ns['allowed'](record,field,i,sub,edid) is None:continue
                    if not value.endswith(b'\0') or b'\0' in value[:-1]:continue
                    try:text=value[:-1].decode('utf-8')
                    except UnicodeDecodeError:continue
                    counts['installed_plugin_text_fields']+=1
                    found.extend(inspect(text,dict(kind='live_plugin',target=target,key=[record,fid,field,index],edid=edid)))
        walk(0,len(raw))
    manifest=json.loads((args.repo/'installer-data/manifest.json').read_text(encoding='utf-8'))
    for op in manifest['operations']:
        p=args.game/op['target']
        if p.suffix.lower() in ('.strings','.dlstrings','.ilstrings') and p.is_file():
            counts['installed_strings_files']+=1
            for sid,text,_ in read_strings(p.read_bytes(),p.suffix.lower()):
                counts['installed_strings_rows']+=1;found.extend(inspect(text,dict(kind='live_strings',target=op['target'],key=sid)))
        if op['kind']=='copy' and p.is_file():
            data=p.read_bytes();text=data.decode('utf-16') if data[:2] in (b'\xff\xfe',b'\xfe\xff') else data.decode('utf-8-sig')
            counts['ui_or_bat_files']+=1
            for number,line in enumerate(text.splitlines(),1):
                if p.suffix.lower()=='.bat':
                    match=re.match(r'\s*(?:echo\s+|set\s+/p\s+[^=]+=)(.*)',line,re.I)
                    if not match:continue
                    value=match[1]
                else:
                    if '\t' not in line:continue
                    _,value=line.split('\t',1)
                found.extend(inspect(value,dict(kind='ui_or_bat',target=op['target'],line=number)))
    for p in args.sst_dir.glob('*.sst'):
        _,rows=parse(p.read_bytes());counts['sst_files']+=1
        for r in rows:
            inactive=bool(r['flags']&(2|4|64|128));counts['inactive_sst_rows' if inactive else 'active_sst_rows']+=1
            found.extend(inspect(r['translation'],dict(kind='inactive_sst' if inactive else 'active_sst',sst=p.name,key=r['key'],flags=r['flags'])))
    unique={}
    for r in found:
        if r['location']['kind'] in ('inactive_sst','active_sst'):continue
        unique.setdefault((r['inner'],r['context']),r)
    result=dict(counts=counts,bracket_candidates=Counter(r['location']['kind'] for r in found),image_caption_candidates=sum(r['section']=='image_caption' for r in found),unique_live_contexts=len(unique))
    (args.output/'locations.json').write_text(json.dumps(found,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (args.output/'unique-live-contexts.json').write_text(json.dumps(list(unique.values()),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (args.output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
