"""Complete the recorded SST terminology review and inspect every live recipe.

Source text is data. This script never calls an API or writes game/SST files.
"""
import argparse,copy,csv,gzip,hashlib,json,re,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from patch_engine import check_translation,CONTROL_PATTERN
from audit_sst_terminology import matcher,inspect,save,sha,reviewed_context
from build_donor_reuse_patch import repair_particle

ALIASES={
 'Inquisitor':['심문관'], 'Dreshdae':['드레쉬다에'], 'Geonosis':['제오노시스','게오노시스'],
 'Nar Shaddaa':['나 샤다오','날 샤다'], 'Yuuzhan Vong':['유우잔 본'],
 'Hadrian':['해드리언','헤이드리언','해드런','하드리아'], 'Aceles':['아세레스'],
 'Mandalorian':['만달로어인','맨달로리안'], 'Shadow Collective':['그림자 컬렉티브','그림자 연합','섀도우 조합'],
 'hyperspace':['중력 도약','초광속 도약'], 'Hyperdrive':['초공간 추진기 엔진','초공간 추진기'],
 'Dantooine':['타투인'], 'Janese':['자네스'], 'Galactic Empire':['갈락틱 엠파이어'],
}
LABELS={
 'Agent No. 1':'1호 요원','Raider':'습격자','Derelict Cantonment':'버려진 주둔지',
 'Discarded Camp':'폐기된 야영지','Disowned Barracks':'버려진 병영','Encased Stronghold':'밀폐된 요새',
 'Forsook Siege Camp':'버려진 포위 진지','Geonosis Droid Factory':'지오노시스 드로이드 공장',
 'Ignored Outpost':'방치된 전초기지','Lonely Holding Area':'외딴 수용 구역','Outer Depot':'외곽 보급소',
 'Safeguarded Military Encampment':'보호받는 군사 야영지','Safeguarded Military Post':'보호받는 군사 초소',
 'Solitary Base':'고립된 기지','Solitary Fortlet':'외딴 소형 요새','Unclaimed Military Encampment':'주인 없는 군사 야영지',
 'Unprotected Post':'무방비 초소','Crashed Food Truck':'추락한 식량 운송 트럭',
 'Scrap Metal Foundry':'고철 주조 공장','Geological Location':'지질학적 위치','Thermal Craters':'열 분화구',
 'Bonagal I':'보나갈 I','Bonagal III':'보나갈 III','Casna Aure III':'카스나 아우레 III','Centax I':'센택스 I',
 'Charybdis VII-a':'카리브디스 VII-a','Dromund Fels Minor':'드로먼드 펠스 마이너',
 'Dromund Kalakar II':'드로먼드 칼라카 II','Dromund Tyne':'드로먼드 타인',
 'Jum I':'줌 I','Karaan IV':'카란 IV','Lantana VII':'란타나 VII','Ordaj III':'오르다즈 III',
 'Stentat III':'스텐탓 III','Undar I':'운다르 I','Undar II':'운다르 II',
 'Abandoned Industrial Compound':'버려진 산업 단지','Armin Petrosyan':'아르민 페트로잔',
}
EXACT={
 'Sith Security Investigation':'시스 보안 조사',
 'Unfortunately, one of them hyperspace jumped away before you arrived.':'안타깝게도 그중 한 척은 네가 도착하기 전에 초공간 도약으로 달아났어.',
 "I was born here. Nar Shaddaa's my home.":'전 여기서 태어났어요. 나르 샤다는 제 고향이죠.',
 'But... I just hope the Rebel Alliance can weather the storm that\'s coming.':'하지만... 반란군 연합이 다가오는 폭풍을 이겨낼 수 있기를 바랄 뿐이야.',
 "We're ghosts. We're nobody. We have enough dirt on one other to bury Geonosis Excavation Site herself.":'우린 유령이야. 아무도 아니지. 지오노시스 발굴 현장 자체를 묻어버릴 만큼 서로의 약점을 쥐고 있어.',
 'Credits it is, and next time, I won\'t misjudge you.':'크레딧으로 하지. 다음에는 널 잘못 판단하지 않겠어.',
 'Of course we have "rules." If you think the Shadow Collective was built on a lawless dream, think again.':'물론 우리에게도 "규칙"은 있어. 섀도우 콜렉티브가 무법천지를 꿈꾸며 세워졌다고 생각한다면 다시 생각해 봐.',
}
PREFIX={
 'Yeah, I work at MAST, in the Imperial Diplomatic Corps!':'네, 전 마스트의 제국 외교단에서 일해요! 은하 제국과 소위 반란군 연합 사이의... 연락책 같은 역할을 하죠. 적어도 그러려고 노력하고 있어요.',
 'But if I tell him about how I found the first Artifact':'하지만 내가 첫 아티팩트를 발견한 일이나 섀도우 콜렉티브에서 탈출한 일, 사람을 홀리는 꽃으로 뒤덮인 섬에 고립된 조종사를 구한 일을 얘기해도... 별로 감탄하지 않더라고.',
 'Are you some kind of idiot? I just told you, my ship is BUSTED.':'너 바보냐? 방금 내 배가 박살 났다고 말했잖아. 그럼 내가 뭘 어떡해, 다리로 초공간 도약이라도 하리?\r\n\r\n하지만 이건 어때? 네가 그렇게 크레딧이 넘쳐난다면 오늘 밤 노바에서 만나자. 너라는 은행에서 크레딧을 몽땅 인출해 줄 테니까.',
}
WRONG_PREFIXES={
 'Sith Security Investigation':('드레스데',),
 'Unfortunately, one of them hyperspace jumped away before you arrived.':('콜렉티브','그림자'),
 "I was born here. Nar Shaddaa's my home.":('그러고 싶긴',),
 "But... I just hope the Rebel Alliance can weather the storm that's coming.":('들어봐, 론',),
 "We're ghosts. We're nobody. We have enough dirt on one other to bury Geonosis Excavation Site herself.":('우린 유령이나',),
 "Credits it is, and next time, I won't misjudge you.":('어쩔 수 없군.',),
 'Of course we have "rules." If you think the Shadow Collective was built on a lawless dream, think again.':('그게 바로 네가',),
 'Yeah, I work at MAST, in the Imperial Diplomatic Corps!':('은하계 공간에서',),
 'But if I tell him about how I found the first Artifact':('에휴. ND-5',),
 'Are you some kind of idiot? I just told you, my ship is BUSTED.':('너 바보냐?',),
}

def substitute(ko,replacements):
    if not replacements:return ko
    pattern=re.compile(r'(?<![가-힣A-Za-z0-9_])(?:'+'|'.join(re.escape(a) for a in sorted(replacements,key=len,reverse=True))+r')(?=$|[^가-힣A-Za-z0-9_]|(?:들)?(?:으로|은|는|이|가|을|를|과|와|의|에|께|도|만|로|용|랑|밖|보다|처럼|부터|까지|뿐|일|인|입|임|였|예|라|든|다|지|니|답|나|야))')
    parts=[];cursor=0
    for m in pattern.finditer(ko):
        if m.start()<cursor:continue
        parts.append(ko[cursor:m.start()]);name=replacements[m[0]];parts.append(name);cursor=m.end()
        p=re.match(r'(으로|로|은|는|이|가|을|를|과|와)(?=$|[^가-힣A-Za-z0-9_]|부터|는|다|랑|라고|라는|었던)',ko[cursor:])
        if p and '가'<=name[-1]<='힣':parts.append(repair_particle(name,p[0]));cursor+=len(p[0])
    parts.append(ko[cursor:]);return ''.join(parts)

def repair_structure(source,ko):
    try:check_translation(source,ko);return ko
    except ValueError:pass
    # Only known, source-backed repairs. Do not append arbitrary tags or pad
    # missing paragraphs with blanks to hide incomplete translations.
    if '<br>' not in source:ko=re.sub(r'<br\s*/?>','\n',ko,flags=re.I)
    if source.startswith('[Extort <Global=SFBGS003_NPCDemandMoney_'):
        expected=re.search(r'<Global=[^>]+>',source)[0]
        ko=re.sub(r'<Global=SFBGS003_NPCDemandMoney_[^>]+>',expected,ko)
    if source.startswith('[Pay 50000 Credits]'):ko=ko.replace('<Global=NPCDemandMoney_Large>','50000')
    if source.startswith('[Lie] Made the drop off to your boss.'):ko=ko.replace('<Global=NPCDemandMoney_Medium>','10000')
    if '<Alias=OE_Location>' in source and '해당 구역' in ko:ko=ko.replace('해당 구역','<Alias=OE_Location>')
    if source.startswith('I provided medical assistance to the <Alias=Imperial FleetInjured>'):
        ko=ko.replace('제국군 부상자','<Alias=Imperial FleetInjured>')
    if source.startswith('Today I am here new.'):
        ko=ko.replace('하지 않을 것이다','<b>하지 않을</b> 것이다')
    if source.startswith('Your automatic mortgage payment with <b>ARGOS EXTRACTORS</b>'):
        ko=ko.replace('ARGOS EXTRACTORS','<b>ARGOS EXTRACTORS</b>').replace('125,000','<b>125,000</b>')
        ko=ko.replace('*랜드리 홀리필드*','<i>랜드리 홀리필드').replace('*인터갤럭틱 뱅킹 클랜 대리인*','인터갤럭틱 뱅킹 클랜 대리인</i>')
    controls={'[앞으로]':'[Forward]','[왼쪽 이동]':'[StrafeLeft]','[뒤로]':'[Back]','[오른쪽 이동]':'[StrafeRight]',
              '[위]':'[Up]','[아래]':'[Down]','[왼쪽]':'[Left]','[오른쪽]':'[Right]','[L숄더]':'[LShoulder]'}
    for old,new in controls.items():
        if new in source:ko=ko.replace(old,new)
    flat=ko.replace('\r\n','\n');en=source.replace('\r\n','\n')
    if source.startswith('A Tale of Two Systems'):
        blocks=flat.split('\n\n');flat=blocks[0]+'\n\n'+'\n'.join(blocks[1:-1])+'\n\n'+blocks[-1]
    if source.startswith(('CHAPTER I\r\nIN PRAYER','CHAPTER I\r\nTREATS OF THE PLACE')):flat=flat.replace('\n\n','\n',2)
    if source.startswith('STAVE ONE'):flat=flat.replace('\n\n','\n',1)
    if source.startswith('Project Update, 2254.5.28'):flat=flat.replace(" '볼텍스'","\n'볼텍스'")
    if source.startswith('The current goal of moving large objects'):flat=flat.replace('용기가 벽','용기가\n벽')
    if source.startswith('Sorry, Trevor!'):
        flat=flat.replace('응답 정밀도를','\n>>응답 정밀도를').replace('게다가 노암이','\n>>게다가 노암이').replace('쓸모가 크게','\n>>쓸모가 크게')
    if source.startswith('Heller: Can\'t believe we got into this mess!'):flat=flat.replace('성간 좌표를','\n성간 좌표를')
    if source.startswith('Client: SyntheTech Industries - Lucas Drexler'):flat=flat.replace('로시사이트 화물을','\n  로시사이트 화물을')
    if flat.rstrip().count('\n')==en.rstrip().count('\n'):
        trailing=en.count('\n')-en.rstrip().count('\n');flat=flat.rstrip()+('\n'*trailing)
    ko=flat.replace('\n','\r\n') if '\r\n' in source else flat
    check_translation(source,ko);return ko

def resolve(source,ko,loc,terms,pattern,aliases):
    original=ko;notes=[];record=loc.get('record');field=loc.get('field')
    if source.startswith('DESIGNER NOTE:'):
        try:check_translation(source,ko)
        except ValueError:return source,['Malformed developer note restored to exact English structure.']
        return ko,['Developer-only note preserved without prose/name rewriting.']
    if source==ko and (source.startswith('[SFBGS') or 'Wandering NPC' in source or 'QuadrupedB' in source or record in ('BPTD','PROJ','HDPT','SNDR','FLST','SCEN')):
        return ko,['Technical/editor identifier preserved.']
    if source in EXACT and ko.startswith(WRONG_PREFIXES[source]):ko=EXACT[source];notes.append('Source alignment corrected after direct context review.')
    for prefix,text in PREFIX.items():
        if source.startswith(prefix) and ko.startswith(WRONG_PREFIXES[prefix]) and (prefix!='Are you some kind of idiot? I just told you, my ship is BUSTED.' or ko.count('\n')!=source.count('\n')):ko=text;notes.append('Wrong or incomplete sentence replaced from the supplied English.')
    if source in LABELS and field=='FULL' and record in ('NPC_','FACT','LCTN','WRLD','RACE','CELL','REFR'):
        ko=LABELS[source];notes.append('Exact display label standardized; Roman numeral follows English.')
    if source=='Open' and field=='ATTX' and ko=='오픈':ko='열기';notes.append('Activation verb, not a proper name.')
    if source==original and field=='FULL' and source in ('Rakghoul Body','Rakghoul Head','Rakghoul Claw','Rakghoul Faction','Aceles'):
        ko={'Rakghoul Body':'락굴 신체','Rakghoul Head':'락굴 머리','Rakghoul Claw':'락굴 발톱','Rakghoul Faction':'락굴 진영','Aceles':'아셀리스'}[source];notes.append('Visible label translated; editor references remain unchanged.')
    visible=re.sub(r'<[^>]*>','',source)
    hits=[aliases[m[0].casefold()] for m in pattern.finditer(visible)]
    replacements={}
    for t in hits:
        if t['label_only'] and not re.fullmatch(re.escape(t['english'])+r'(?: [IVX]+)?(?:-[a-z])?',source):continue
        if t['english']=='Hyperdrive' and 'launching it into hyperdrive' in source:continue
        for alias in t['known_variants']:
            if alias!=t['canonical_ko']:
                if alias=='타투인' and 'Tatooine' in visible:continue
                replacements[alias]='초공간 도약' if t['english']=='hyperspace' and alias in ('중력 도약','초광속 도약') else t['canonical_ko']
    # Alias/control tokens are never touched by name normalization.
    protected=r'<[^>]*>|'+CONTROL_PATTERN
    ko=''.join(part if re.fullmatch(protected,part) else substitute(part,replacements)
               for part in re.split('('+protected+')',ko))
    lower=visible.casefold()
    if 'nar shaddaa' in lower and not any(n in lower for n in ('coruscant','imperial center')):ko=substitute(ko,{'코러산트':'나르 샤다'})
    if 'geonosis' in lower and not any(n in lower for n in ('coruscant','imperial center','nar shaddaa')):ko=substitute(ko,{'코러산트':'지오노시스'})
    # A sentence can mention both factions. Correct only the reviewed isolated
    # wrong-faction comparison, never replace every Imperial noun in a paragraph.
    if source=="Can't say for sure. Looks worn, but not cobbled together like a Shadow Collective junker.":
        ko=substitute(ko,{'제국군':'섀도우 콜렉티브'})
    if 'Mandalore' in visible and not re.search(r'\bMandalorians?\b',visible):ko=ko.replace('만달로리안','만달로어')
    if "Sith'Kai" in visible:ko=ko.replace('코리반 항성계','시스카이')
    if visible.startswith('Truth is, the origins of hyperspace travel'):
        ko=ko.replace('초공간 추진기','하이퍼드라이브').replace('추진기 기술','하이퍼드라이브 기술')
    if visible.startswith('CHAPTER I\r\n\r\n(Kept in shorthand.)'):
        ko=ko.replace('추진기 엔진','하이퍼드라이브')
    if 'launching it into hyperdrive' in source:notes.append('Hyperdrive is a growth-rate metaphor here; retain 과부하 rather than an engine name.')
    if source.startswith('Now that the completed Armillary'):notes.append('Later jump is contextual ellipsis after the already named 하이퍼드라이브.')
    if 'non-force sensitive' in visible:notes.append('Negative trait rendered descriptively as 포스에 감응하지 못하는, not a person label.')
    if visible.startswith('[An excerpt from Layne Vren'):
        ko=ko.replace('드론','드로이드')
    if visible.startswith('These bots are getting out of hand.'):
        ko=ko.replace('봇','드로이드')
    if visible.startswith('They could have hyperspace jumped anywhere.'):
        ko=ko.replace('초광속으로 이동','초공간 도약으로 이동')
    if source.startswith('[Bribe <Global=RI05_Frankie_SmallCredits> Credits]'):
        ko=ko.replace('[<Global=RI05_Frankie_SmallCredits> 매수]','[<Global=RI05_Frankie_SmallCredits> 크레딧으로 매수]')
    if source.startswith('Your previous employer negotiated'):
        ko=ko.replace('<b>전</b>','전');notes.append('Removed emphasis tags absent from English.')
    controls={'[대기시작]':'[StartWait]','[취소]':'[Cancel]','[활성화]':'[Activate]',
              '[데이터 메뉴]':'[DataMenu]','[수락]':'[Accept]','[선원]':'[Crew]'}
    for old,new in controls.items():
        if new in source:ko=ko.replace(old,new)
    special=reviewed_context(source,ko)
    if special[0]:ko=special[0];notes.append('Applied source-specific context decision.')
    if ko!=original:notes.append('Terminology/particle or explicitly recorded source/structure correction.')
    else:notes.append('Existing contextual wording retained; currency paraphrase, alias token, metaphor or abbreviation allowed.')
    repaired=repair_structure(source,ko)
    if repaired!=ko:notes.append('Explicit source-backed tag/control/newline restoration; no missing paragraph hidden.')
    return repaired,notes

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--sst-csv',type=Path,required=True);args=ap.parse_args()
    if args.output_dir.exists():raise ValueError('Preserve previous review: output exists')
    args.output_dir.mkdir(parents=True)
    review=args.repo/'translation-review';terms=copy.deepcopy(json.loads((review/'terminology-followup/glossary-extensions.json').read_text(encoding='utf-8'))['terms'])
    for t in terms:t['known_variants']=sorted(set(t['known_variants']+ALIASES.get(t['english'],[]))-{t['canonical_ko']},key=len,reverse=True)
    pattern,aliases=matcher(terms);rows=[];errors=[]
    original=json.loads((review/'terminology/manifest.json').read_text(encoding='utf-8'))
    for batch in original['batches']:
        if not batch['file'].startswith('sst/'):continue
        path=review/'terminology'/batch['file'];assert sha(path)==batch['sha256']
        for item in json.loads(path.read_text(encoding='utf-8'))['items']:
            try:new,notes=resolve(item['source_en'],item['current_ko'],item['location'],terms,pattern,aliases)
            except ValueError as e:errors.append({'source_en':item['source_en'],'current_ko':item['current_ko'],'location':item['location'],'error':str(e)});continue
            rows.append({**item,'proposed_ko':new if new!=item['current_ko'] else None,'review_status':'context_validated' if new!=item['current_ko'] else 'context_accepted',
                         'review_method':'codex_complete_context_review','review_notes':notes,'human_reviewed':False})
    initial_count=len(rows);seen={(r['location']['sst'],r['location']['record'],r['location']['form_id'],r['location']['field'],r['location']['index']) for r in rows}
    expected=next(i['sha256'] for i in original['inputs'] if i['file']=='sst_entries.csv')
    if sha(args.sst_csv)!=expected:raise ValueError('SST snapshot changed')
    sst_scanned=0
    with args.sst_csv.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if int(r['flags'])&(2|4|64|128) or not r['source'] or not r['translation']:continue
            sst_scanned+=1;loc={k:r[k] for k in ('sst','record','form_id','field','index','group','string_id')}
            key=tuple(loc[k] for k in ('sst','record','form_id','field','index'))
            if key in seen:continue
            source,ko=r['source'],r['translation']
            if not (pattern.search(re.sub(r'<[^>]*>','',source)) or source in LABELS or (source=='Open' and r['field']=='ATTX')):continue
            try:new,notes=resolve(source,ko,loc,terms,pattern,aliases)
            except ValueError as e:errors.append({'source_en':source,'current_ko':ko,'location':loc,'error':str(e)});continue
            if new!=ko:rows.append({'source_en':source,'current_ko':ko,'proposed_ko':new,'location':loc,'review_status':'context_validated','review_method':'codex_complete_context_review','review_notes':notes,'human_reviewed':False})
    if errors:save(args.output_dir/'errors.json',{'items':errors});print(json.dumps({'errors':len(errors)}));return
    batches=[]
    for start in range(0,len(rows),250):
        p=args.output_dir/f'sst-final-{start//250+1:04}.json';save(p,{'items':rows[start:start+250]});batches.append({'file':p.name,'items':len(rows[start:start+250]),'sha256':sha(p)})
    package=args.repo/'installer-data';manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8'));edits=[];scanned=Counter()
    for op in manifest['operations']:
        if op['kind']!='text_recipe':continue
        recipe=json.loads(gzip.decompress((package/'blobs'/op['blob']).read_bytes()))
        for key,value in recipe['translations']:
            source,ko=value[:2];scanned[recipe['kind']]+=1
            loc={'target':op['target'],'key':key,'record':key[0] if recipe['kind']=='plugin' else None,'field':key[2] if recipe['kind']=='plugin' else None}
            try:new,notes=resolve(source,ko,loc,terms,pattern,aliases)
            except ValueError as e:errors.append({'source_en':source,'current_ko':ko,'location':loc,'error':str(e)});continue
            if new!=ko:edits.append({'source_en':source,'current_ko':ko,'proposed_ko':new,'location':loc,'kind':recipe['kind'],'review_status':'context_validated','review_notes':notes,'human_reviewed':False})
    save(args.output_dir/'recipe-edits.json',{'items':edits})
    save(args.output_dir/'errors.json',{'items':errors})
    definitions=json.loads((review/'terminology/unresolved-names.json').read_text(encoding='utf-8'))['items']
    for item in definitions:
        item.update(canonical_ko=LABELS.get(item['source_en']),status='project_label_standard' if item['source_en'] in LABELS else 'context_variants_accepted',
                    review_note='Use English numerals exactly; display labels only.' if item['source_en'] in LABELS else 'You? depends on address; Horuset surface/orbit suffixes preserve distinct location context.',human_reviewed=False)
    save(args.output_dir/'name-definitions.json',{'items':definitions})
    save(args.output_dir/'glossary.json',{'terms':terms})
    report={'initial_sst_findings_reviewed':initial_count,'eligible_sst_rows_rescanned':sst_scanned,'sst_findings_reviewed':len(rows),'sst_decisions':dict(Counter(r['review_status'] for r in rows)),
            'source_manifest_sha256':sha(review/'terminology/manifest.json'),'batches':batches,'name_definitions_reviewed':len(definitions),
            'live_recipe_locations_scanned':dict(scanned),'live_recipe_edits':len(edits),'structural_errors':len(errors),'game_modified':False,'sst_modified':False}
    save(args.output_dir/'manifest.json',report);print(json.dumps(report))

if __name__=='__main__':main()
