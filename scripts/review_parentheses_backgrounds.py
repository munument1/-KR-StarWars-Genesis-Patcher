"""Review redundant bilingual glosses and character background register only."""
import argparse,gzip,json,re,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apply_reviewed_sst import parse
from patch_engine import check_translation,read_strings
from installer_backend import sha

# Explicitly reviewed display glosses. Symbols, IDs, summaries and wordplay are
# deliberately absent; never infer redundancy merely from Latin characters.
REMOVE=set('''Aegis|Among the Hyperspace Jumps|Arthur|Ascendancy|Bayu the Hutt|Being|BioTech Industries|BlasTech|Cade|Cade Ordo|Carnivore|Chunks|Collective|DRONE|Dantoo Town|Dantooine|DarkStar Astrodynamics|Dealing with Corruption|Degaussing|Eye|Falkland Systems|Fight or Flight|GNN|GalacTalk|Galactic Colonization Act|Gallofree|Geonosis|Gland|Good|Grand Moff Tarkin|Hadrian|Heal Gel|Hephaestus|Herbivore|Hutt|ICS|ISB|ISC|Imperial Center|InterGalactic Banking Clan|Jeong|Juma juice|Kessel|Key|Kijimi|Kuat Drive Yards|LIST|Lazarus|Lunar Droidics|Mandalore's Legacy|Meeka|Mei|Middle C|Milena|Min|NCI|Nar Shaddaa|OFF|ON|Omnivore|Orlase|Outer Rim|POI|Partisans|Percival|Ragana|Rakghoul|Rebel Alliance|Red Devils|Revanite|Rim|Ron Gallofree|Ryll|RESTART|SAVE|Samson Cebrail|Sanon|Savior|Saxon|Scavs|Shadow Collective|Shak'kra ven dross|Ship Vendor Framework|Sith|Smuggler's Outpost|Sol|Spice|Suicide king|SyntheTech Industries|Taris|Taris Savior Award|The Key|The Lock|The Rock|Trade Federation|Tranquilitea|Truth|Undercity|Unknown Regions|Urrqal|Vergence|Vergence Scatter|Veshh ka'nik|Vladimir|Vong|Voxyn|Yasin|Yuuzhan Vong|Zoe Kaminski|clutter|hermanita|holobook|skein cell|slicer|trash|vod'''.split('|'))
REVERSE={'NCI(신경 제어 인터페이스)':'신경 제어 인터페이스',
 'DRIP(방위 연구 및 이니셔티브 프로그램)':'방위 연구 및 이니셔티브 프로그램',
 'CAPS(완전 자동 조종 시스템)':'완전 자동 조종 시스템',
 'exertion(노력)':'노력','STAP(1인용 정찰 플랫폼)':'1인용 정찰 플랫폼',
 'BARC(바이크 정찰 코만도)':'바이크 정찰 코만도'}
REMOVE.update(('Vandor-3','ECS','LSS','TCS','XP','INV','PCR','PTO','TTM','XNN','DITAS'))
BACKGROUND={
 '0022EC6E':('The Galaxy is home to untold alien species.', '은하계는 수많은 외계 종족의 고향입니다. 거대한 짐승이든 작은 생물이든, 당신은 그들을 찾아 연구하고 그들이 제공하는 모든 선물을 얻었습니다.'),
 '0022EC7B':('An elected voice in a fractured era,', '분열된 시대의 선출된 목소리로서, 당신은 지렛대와 막후 협상을 통해 짧은 휴전, 구호 경로, 생명을 구하는 교환을 성사시킵니다.'),
 '0022EC71':('Years spent mapping posture and leverage', '자세와 지렛대 원리를 연구하며 보낸 세월은 당신에게 균형이 무너지는 지점을 가르쳐 주었습니다. 어깨의 위치나 무릎의 느슨함 같은 작은 징후를 읽고 싸움을 끝낼 관절을 노립니다. 효율성이 당신의 철학입니다.'),
 '0022EC7F':('An Imperial blockade starved your homeworld', '제국군의 봉쇄로 당신의 고향 행성은 식량 수입이 끊겨 굶주렸습니다. 당신은 배급량을 조절하고, 남은 찌꺼기를 재활용하고, 엄격한 일정과 청결한 조리로 사람들을 먹여 살렸습니다.'),
 '0022EC76':('From the Wampas to the Rancor,', '왐파부터 랭코까지, 적대적이고 이국적인 야수들이 은하계 전역에 퍼져 있습니다. 당신은 그들을 추적하고, 발견하고, 제압하는 기술을 배웠습니다.'),
}
PARENS=re.compile(r'[（(]([^()（）]*)[)）]')
TOKENS=re.compile(r'<[^>]*>|\[[^\]]*\]|\{\d+\}')

def clean_glosses(ko):
    # Work only in display text, preserving exact control tags and attributes.
    def clean(text):
        for old,new in REVERSE.items():text=re.sub(r'(?<![A-Za-z])'+re.escape(old),lambda _:new,text)
        def replace(m):
            if m[1].strip() not in REMOVE:return m[0]
            if not re.search(r'[가-힣][\s\"\'”’]*$',text[:m.start()]):return m[0]
            return ''
        return PARENS.sub(replace,text)
    pieces=[];pos=0
    for m in TOKENS.finditer(ko):pieces.extend((clean(ko[pos:m.start()]),m[0]));pos=m.end()
    pieces.append(clean(ko[pos:]));return ''.join(pieces)

def resolve(source,ko,loc):
    new=clean_glosses(ko);reasons=[]
    if new!=ko:reasons.append('redundant_bilingual_gloss')
    fid=loc.get('form_id')
    if loc.get('record')=='PERK' and loc.get('field')=='DESC' and fid in BACKGROUND:
        prefix,value=BACKGROUND[fid]
        if source.startswith(prefix):new=value;reasons.append('character_background_polite_register')
    if new!=ko:
        # Two legacy XP tutorial SST entries use HTML breaks for plain-text
        # CRLFs. Their current installer recipes already have correct breaks.
        if source.startswith(('Completing a variety of actions, such as defeating enemies','Throughout your journey, you will be awarded Experience Points')) and '<br>' in new and '<br>' not in source:
            new=new.replace('<br>','\r\n' if '\r\n' in source else '\n');reasons.append('legacy_tutorial_line_break_repair')
        check_translation(source,new)
    return new,reasons

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--sst-dir',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True);items=[];recipe_edits=[];candidates=[];snapshot=[];counts=Counter();backgrounds=[]
    def inspect(source,ko,loc):
        new,reasons=resolve(source,ko,loc)
        item=dict(source_en=source,current_ko=ko,proposed_ko=new if new!=ko else None,location=loc,review_status='context_validated' if new!=ko else 'context_keep',reasons=reasons,human_reviewed=False)
        if re.search('[가-힣]',ko) and any(re.search('[A-Za-z]{2}',m[1]) for m in PARENS.finditer(TOKENS.sub('',ko))):candidates.append(item)
        if new!=ko:items.append(item) if loc['kind']=='sst' else recipe_edits.append(item)
        if loc.get('record')=='PERK' and loc.get('field')=='DESC' and loc.get('form_id') and 0x22ec6d<=int(loc['form_id'],16)<=0x22ec81:backgrounds.append(item)
    for p in sorted(args.sst_dir.glob('*.sst')):
        raw=p.read_bytes();snapshot.append(dict(sst=p.name,sha256=sha(raw)));_,rows=parse(raw);counts['sst_files']+=1
        for row in rows:
            if row['flags']&(2|4|64|128):continue
            counts['sst_rows']+=1;loc=dict(zip(('group','string_id','form_id','record','field','index'),row['key']));loc.update(kind='sst',sst=p.name)
            inspect(row['source'],row['translation'],loc)
    manifest=json.loads((args.repo/'installer-data/manifest.json').read_text(encoding='utf-8'))
    for op in manifest['operations']:
        raw=(args.repo/'installer-data/blobs'/op['blob']).read_bytes()
        if op['kind']=='text_recipe':
            recipe=json.loads(gzip.decompress(raw))
            for key,values in recipe['translations']:
                counts['recipe_rows']+=1;loc=dict(kind=recipe['kind'],target=op['target'],key=key)
                if isinstance(key,list):loc.update(record=key[0],form_id=f'{key[1]:08X}',field=key[2])
                inspect(values[0],values[1],loc)
        elif op['kind']=='fallback_strings':
            for sid,ko,_ in read_strings(raw,Path(op['target']).suffix):
                counts['fallback_rows']+=1
                # No English pair in this raw supplement. Audit only; do not
                # treat a Korean original as an English source for editing.
                if any(re.search('[A-Za-z]{2}',m[1]) for m in PARENS.finditer(TOKENS.sub('',ko))):candidates.append(dict(source_en=None,current_ko=ko,proposed_ko=None,location=dict(kind='fallback',target=op['target'],key=sid),review_status='context_keep',reasons=['original_quote_etymology_or_technical_code'],human_reviewed=False))
    save(args.output/'source-verification.json',{'files':snapshot})
    save(args.output/'sst-final-0001.json',{'items':items});save(args.output/'recipe-edits.json',{'items':recipe_edits});save(args.output/'candidates.json',{'items':candidates});save(args.output/'character-backgrounds.json',{'items':backgrounds})
    save(args.output/'glossary.json',{'remove_redundant_glosses':sorted(REMOVE),'reverse_glosses':REVERSE,'preserve':'summaries, chemical symbols, IDs, protected controls, wordplay and meaningful abbreviations'})
    save(args.output/'manifest.json',dict(schema_version=1,counts=dict(counts),sst_changed=len(items),recipe_changed=len(recipe_edits),candidate_locations=len(candidates),structural_errors=[],batches=[dict(file='sst-final-0001.json',sha256=sha((args.output/'sst-final-0001.json').read_bytes()))]))
    print(json.dumps(dict(counts=counts,sst_changed=len(items),recipe_changed=len(recipe_edits),reasons=Counter(reason for r in recipe_edits for reason in r['reasons']))))

if __name__=='__main__':main()
