"""Create a source-backed project glossary and audit every eligible SST + live recipe."""
import argparse,csv,gzip,hashlib,json,re,sys
from collections import Counter,defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from patch_engine import check_translation
from build_three_way_candidates import alias_pattern
from build_donor_reuse_patch import repair_particle

SPELLINGS={
 'blaster':['블래스터'], 'lightsaber':['라이트세이버','라이트 세이버','광검'],
 'Rebel Alliance':['반란군 동맹','반군 연합','반란 연합'], 'hyperspace':['하이퍼스페이스','하이퍼 스페이스'],
 'Yuuzhan Vong':['유잔 봉','유우잔봉'], 'Hutt Cartel':['헛 카르텔','후트 카르텔','허트카르텔'],
 'Grand Moff':['그랜드 모프'], 'Grand Admiral':['그랜드 제독','그랜드 애드미럴','대장군'],
 'Tython':['타이톤'], 'Geonosis':['게오노스','지오노스','게오노시'], 'Star Wars Genesis':['스타 워즈 제네시스'],
 'Coruscant':['코러스칸트','코루스칸트','코르산트'],
 'Nar Shaddaa':['나르샤다','나 샤다','나르 샤다아'],
 'Rakghoul':['라크굴','라크구울','락구울'],
 'Shadow Collective':['섀도 콜렉티브','섀도우 컬렉티브','그림자 집단'],
 'Thrawn':['스론','쓰라운'], 'Kallus':['칼루스'],
 'Percival / Pervical':['퍼시발'], 'Hadrian':['해드라이언','하드리안','해드리안','헤드리안','해드리아스','하드리아누스'],
 'Aceles':['아세셀','아셀스'], 'Londinion':['런디니온'], 'Orlase':['올라스','올레이스'],
 'Jinan':['지넌'], 'Vigilance':['비질런트'],
 'Dreshdae':['드레슈다내','드레시다이','드레슈다이','드레쉬다이','드레시다','드레시데','드레쉬데','드레슈다에','드레시다에'],
 'Scaled Citadel':['비늘의 성채','비늘 시타델','비늘 성체'],
 'Gamorrean Guard':['가모리안 가드'], 'Hutt Clan':['헛 클랜','후트 클랜','헛 가문','헛 카르텔'],
 'Hutt Clan Enforcer':['헛 클랜 집행자','헛 클랜 엔포서','허트 클랜 엔포서'],
 'Hutt Clan Crimelord':['헛 클랜 범죄 조직 두목','헛 클랜 범죄 두목'],
 'Hutt Clan Hitman':['헛 클랜 청부업자','헛 클랜 킬러'],
 'Partisan Heavy Soldier':['파르티잔 중병'],
 'Dromund':['드러먼드','드루먼드','드로문드'], 'Bonagal':['보나가르','보나가'],
 'Bubbok':['부복'], 'Casna Aure':['카스나 오레'], 'Centax':['센탁스'],
 'Jum':['점'], 'Karaan':['카라안'], 'Kuhurrik':['쿠후릭'], 'Ordaj':['오르다이','올다즈','오르다지'],
 'Ronay':['로나이'], 'Stentat':['스텐탯'], 'Tann':['탠'], 'Undar':['운다'],
}
def term_pattern(values):
    aliases='|'.join(re.escape(v) for v in sorted(set(values),key=len,reverse=True))
    return re.compile(r'(?<![가-힣A-Za-z0-9_])(?:'+aliases+r')(?=$|[^가-힣A-Za-z0-9_]|(?:들)?(?:으로부터|로부터|으로는|로는|에서|에게|부터|까지|으로|은|는|이|가|을|를|과|와|의|에|께|도|만|로|용)(?:$|[^가-힣A-Za-z0-9_]))')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def glossary(path):
    terms=[];section=''
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('## '):section=line[3:]
        if not line.startswith('|'):continue
        cols=[c.strip() for c in line.strip('|').split('|')]
        if len(cols)!=3 or cols[0] in ('영어','---') or not re.search('[가-힣]',cols[1]):continue
        english,ko,note=cols
        english_aliases=english.split(' / ')
        if english in ('blaster','lightsaber','droid','Mandalorian','Inquisitor','Rakghoul'):english_aliases.append(english+'s')
        terms.append({'id':hashlib.sha256(english.encode()).hexdigest()[:16],'english':english,
                      'english_aliases':english_aliases,'canonical_ko':ko,'category':section,
                      'status':'provisional' if '잠정' in note else 'project_standard',
                      'context_required':english in ('Credits','Mandalore','Inquisitor','Force Sensitive','Force Reflexes'),
                      'label_only':english in ('Jum','Undar'),
                      'note':note,'known_variants':SPELLINGS.get(english,[]),'observed_exact_translations':[]})
    if len({t['id'] for t in terms})!=len(terms):raise ValueError('Duplicate glossary term')
    return terms

def matcher(terms):
    aliases={a.casefold():t for t in terms for a in t['english_aliases']}
    pattern=re.compile(r'(?<![A-Za-z0-9_])(?:'+'|'.join(re.escape(a) for a in sorted(aliases,key=len,reverse=True))+r')(?![A-Za-z0-9_])',re.I)
    return pattern,aliases

def inspect(source,translation,pattern,aliases):
    hits={aliases[m[0].casefold()]['id']:aliases[m[0].casefold()] for m in pattern.finditer(source)
          if not (aliases[m[0].casefold()]['english']=='Vigilance' and m[0][0].islower())}
    issues=[]
    for t in hits.values():
        variants=[v for v in t['known_variants'] if term_pattern([v]).search(translation)]
        canonical=t['canonical_ko'] in translation
        if t['english']=='Rebel Alliance' and term_pattern(['반란군']).search(translation):canonical=True
        if variants or not canonical:
            issues.append({'term_id':t['id'],'english':t['english'],'canonical_ko':t['canonical_ko'],
                           'variants_found':variants,'reason':'spelling_variant' if variants else 'canonical_not_found',
                           'context_required':t['context_required'] or t['status']=='provisional'})
    return list(hits),issues

def proposal(source,translation,issues,terms,location):
    by_id={t['id']:t for t in terms};replacements={}
    for issue in issues:
        t=by_id[issue['term_id']]
        if issue['context_required'] or not issue['variants_found']:continue
        if t['label_only']:
            if location['field']!='FULL' or not re.fullmatch(re.escape(t['english'])+r'(?: [IVX]+)?(?:-[a-z])?',source):continue
        for variant in issue['variants_found']:
            if variant in replacements and replacements[variant]!=t['canonical_ko']:return None,'conflicting_aliases'
            replacements[variant]=t['canonical_ko']
    if not replacements:return None,'context_needed'
    # Never alter tag attributes/control tokens. Plain translated text can be normalized.
    for token in re.findall(r'<[^>]*>|\[(?:Accept|Cancel|Activate|Jump|[^\]]*:[0-9]+)\]',translation):
        if any(term_pattern([v]).search(token) for v in replacements):return None,'protected_token_hold'
    pieces=[];cursor=0
    for m in term_pattern(replacements).finditer(translation):
        name=replacements[m[0]];pieces.extend([translation[cursor:m.start()],name]);cursor=m.end()
        particle=re.match(r'(으로|로|은|는|이|가|을|를|과|와)(부터|는)?(?=$|[^가-힣A-Za-z0-9_])',translation[cursor:])
        if particle:pieces.append(repair_particle(name,particle[1])+(particle[2] or ''));cursor+=len(particle[0])
    pieces.append(translation[cursor:]);result=''.join(pieces)
    if result==translation:return None,'context_needed'
    try:check_translation(source,result)
    except ValueError:return None,'structural_hold'
    return result,'rule_validated'

def reviewed_context(source,translation):
    # Source-specific decisions from the remaining live plugin findings, not global replacements.
    if source=='Mandalorian Loyalist' and translation=='만달로어 충성파':return '만달로리안 충성파','context_validated'
    if 'Mandalorian way' in source and '만달로어의 방식' in translation:return None,'context_accepted'
    if source=="The Sith Empire hosts many non-force sensitive individuals." and translation=='시스 제국에는 강력한 포스 능력을 부리지 못하는 일반 백성도 수없이 많이 살아가고 있습니다.':
        return '시스 제국에는 포스에 감응하지 못하는 일반 백성도 수없이 많이 살아가고 있습니다.','context_validated'
    if source=='Force Sensitive Dummy' and translation=='포스 센서티브 더미':return '포스 감응자 더미','context_validated'
    if source=='Force Sensitive' and translation=='포스 센서티브':return '포스 감응','context_validated'
    if source in ('Focused [Force Sensitive Only]','Attuned [Force Sensitive Only]') and '포스 센서티브 전용' in translation:
        return translation.replace('포스 센서티브 전용','포스 감응자 전용'),'context_validated'
    if source=='Janese' and translation=='자니스':return '제니스','context_validated_provisional_name'
    if source in ('Inquisitor Attacks','Inquisitors to use for Inquisitor Attacks quest (One at a time)') and '심판관' in translation:
        return translation.replace('심판관','인퀴지터'),'context_validated'
    if source.startswith("You've done well enough, all things considered. Take your credits.") and '보상을 챙기도록' in translation:return None,'context_accepted'
    if source.startswith('So Bayu the Hutt is now in charge') and '돈도 좀 벌 수' in translation:return None,'context_accepted'
    if 'Galactic Empire marine named Captain Myeong' in source and '제국군 해병대 대위인 명' in translation:return None,'context_accepted'
    return None,None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--audit-dir',type=Path,required=True)
    ap.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--source-verification',type=Path)
    args=ap.parse_args();out=args.output_dir
    if out.exists():raise SystemExit('Output already exists; preserve edits')
    terms=glossary(args.repo/'translation-review/GLOSSARY.md');pattern,aliases=matcher(terms)
    exact=defaultdict(Counter);examples=defaultdict(dict);unlisted=defaultdict(lambda: {'variants':Counter(),'sst':set(),'record_types':set()})
    all_sst=Counter();eligible=Counter();flags=Counter();matched=Counter();sst_issues=[];total=0
    active={Path(r['plugin']).stem.casefold():r['plugin'] for r in read(args.audit_dir/'plugins.csv')}
    for r in read(args.audit_dir/'sst_entries.csv'):
        total+=1;all_sst[r['sst']]+=1
        if int(r['flags'])&(2|4|64|128) or not r['source'] or not r['translation']:
            flags['excluded_flags_or_empty']+=1;continue
        eligible[r['sst']]+=1
        key=r['source'].strip().casefold();term=aliases.get(key)
        if term:
            exact[term['id']][r['translation']]+=1
            examples[term['id']].setdefault(r['translation'],{'sst':r['sst'],'record':r['record'],'form_id':r['form_id'],'field':r['field']})
        if r['record'] in ('NPC_','FACT','LCTN','WRLD','RACE') and r['field']=='FULL' and key not in aliases and len(r['source'])<=80 and re.search('[가-힣]',r['translation']):
            item=unlisted[r['source']];item['variants'][r['translation']]+=1;item['sst'].add(r['sst']);item['record_types'].add(r['record'])
        hit,issues=inspect(r['source'],r['translation'],pattern,aliases)
        matched.update(hit)
        if issues:
            stem=re.sub(r'_en_ko$','',Path(r['sst']).stem,flags=re.I)
            sst_issues.append({'source_en':r['source'],'current_ko':r['translation'],'issues':issues,
                              'location':{k:r[k] for k in ('sst','record','form_id','field','index','group','string_id')},
                              'own_plugin':active.get(stem.casefold()),'review_status':'pending','proposed_ko':None})
    for t in terms:
        t['source_occurrences']=matched[t['id']]
        t['observed_exact_translations']=[{'ko':ko,'occurrences':n,'example':examples[t['id']][ko],'approved_alias':False} for ko,n in exact[t['id']].most_common()]
    unresolved=[{'source_en':source,'record_types':sorted(v['record_types']),'sst_count':len(v['sst']),
                 'variants':[{'ko':ko,'count':n} for ko,n in v['variants'].most_common()],
                 'status':'needs_term_definition','canonical_ko':None}
                for source,v in unlisted.items() if len(v['variants'])>1]
    unresolved.sort(key=lambda r:(-r['sst_count'],-sum(v['count'] for v in r['variants']),r['source_en']))
    manifest=json.loads((args.repo/'installer-data/manifest.json').read_text(encoding='utf-8'));plugin_issues=[];plugin_counts=Counter()
    for op in manifest['operations']:
        if op['kind']!='text_recipe':continue
        recipe=json.loads(gzip.decompress((args.repo/'installer-data/blobs'/op['blob']).read_bytes()))
        if recipe['kind']!='plugin':continue
        plugin_counts[op['target']]=len(recipe['translations'])
        for key,values in recipe['translations']:
            source,translation=values[:2];hit,issues=inspect(source,translation,pattern,aliases)
            if issues:plugin_issues.append({'source_en':source,'current_ko':translation,'issues':issues,
                                            'location':{'target':op['target'],'record':key[0],'form_id':f'{key[1]:08X}','field':key[2],'index':key[3]},
                                            'review_status':'pending','proposed_ko':None})
    decisions=Counter()
    for scope,items in [('sst',sst_issues),('plugin',plugin_issues)]:
        for item in items:
            value,state=proposal(item['source_en'],item['current_ko'],item['issues'],terms,item['location'])
            context_value,context_state=reviewed_context(item['source_en'],item['current_ko'])
            if context_state:
                if context_value is not None:check_translation(item['source_en'],context_value)
                value,state=context_value,context_state
            remaining=inspect(item['source_en'],value,pattern,aliases)[1] if value else item['issues']
            if context_state:remaining=[]
            elif value and remaining:state='partial_rule_validated'
            item.update(proposed_ko=value,review_status=state,human_reviewed=False)
            if context_state:item['review_method']='codex_context_review'
            item['remaining_issues']=remaining
            decisions[scope+'_'+state]+=1
    out.mkdir(parents=True);save(out/'glossary.json',{'schema_version':1,'scope':'Genesis terminology; existing base Korean translation quality is out of scope','terms':terms})
    save(out/'unresolved-names.json',{'items':unresolved})
    batches=[]
    for label,items in [('plugin',plugin_issues),('sst',sst_issues)]:
        folder=out/label;folder.mkdir()
        for start in range(0,len(items),250):
            path=folder/f'{label}-{start//250+1:04}.json';save(path,{'schema_version':1,'items':items[start:start+250]})
            batches.append({'file':path.relative_to(out).as_posix(),'items':len(items[start:start+250]),'sha256':sha(path)})
    report={'schema_version':1,'sst_files':len(all_sst),'sst_rows':total,'eligible_sst_rows':sum(eligible.values()),'excluded_sst_rows':dict(flags),
            'glossary_terms':len(terms),'sst_findings':len(sst_issues),'plugin_recipe_files':len(plugin_counts),
            'plugin_recipe_locations':sum(plugin_counts.values()),'current_plugin_findings':len(plugin_issues),
            'unresolved_name_entries':len(unresolved),'review_decisions':dict(decisions),'batches':batches,
            'sst_inventory':[{'sst':name,'rows':n,'eligible_rows':eligible[name]} for name,n in sorted(all_sst.items())],
            'inputs':[{'file':'sst_entries.csv','sha256':sha(args.audit_dir/'sst_entries.csv')},
                      {'file':'GLOSSARY.md','sha256':sha(args.repo/'translation-review/GLOSSARY.md')},
                      {'file':'installer-data/manifest.json','sha256':sha(args.repo/'installer-data/manifest.json')}],
            'notes':['A canonical spelling absent from a sentence is a review signal, not proof of an error.',
                     'Observed exact translations and frequent variants are evidence, never automatically approved.',
                     'Current plugin findings have priority over old SST findings; the same SST can serve other plugins.',
                     'No game, SST or installer data was changed. No AI API was used.']}
    save(out/'manifest.json',report)
    if args.source_verification:
        verification=json.loads(args.source_verification.read_text(encoding='utf-8'))
        if not verification['all_snapshot_rows_match_current_sst'] or len(verification['files'])!=len(all_sst):raise ValueError('Source snapshot verification failed')
        save(out/'source-verification.json',verification)
        report['source_verification']={'file':'source-verification.json','sha256':sha(out/'source-verification.json'),'verified_sst_files':len(verification['files'])}
        save(out/'manifest.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('batches','sst_inventory','inputs','notes')}))

if __name__=='__main__':main()
