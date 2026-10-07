"""Build a separate patch package using donor text only where English matches exactly."""
import argparse, gzip, hashlib, json, re, shutil, sys
from collections import Counter
from pathlib import Path
from build_three_way_candidates import alias_pattern, name_changes, file_digest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from patch_engine import read_strings, patch_strings, check_translation

def sha(raw):return hashlib.sha256(raw).hexdigest()

def repair_particle(name, particle):
    ending='브' if name=='ND-5' else name[-1]
    if not '가'<=ending<='힣':raise ValueError('Unknown name pronunciation')
    coda=(ord(ending)-ord('가'))%28
    pairs=(('은','는'),('이','가'),('을','를'),('과','와'))
    for consonant,vowel in pairs:
        if particle in (consonant,vowel):return consonant if coda else vowel
    if particle in ('으로','로'):return '으로' if coda not in (0,8) else '로'
    return particle

def adapted_translation(source,donor,target):
    if not donor or not re.search('[가-힣]',donor) or '\ufffd' in donor:return None,'no_korean_donor',[]
    try:check_translation(source,donor)
    except ValueError:return None,'donor_structure_hold',[]
    if source==target:return donor,'unchanged_english',[]
    changes=name_changes(source,target)
    if not changes:return None,'other_english_changes',[]
    replacement={};counts=Counter(c[0] for c in changes);used=[]
    for old,new,aliases,translated in changes:
        aliases=list(aliases)
        if old in ("Va'ruun","House Va'ruun") and new=='Sith':aliases=['바룬 가문','바룬가문','바룬']
        if any(c[0]==old and c[3]!=translated for c in changes):return None,'conflicting_names',[]
        if len(re.findall(r'(?<![A-Za-z0-9_])'+re.escape(old)+r'(?![A-Za-z0-9_])',source))!=counts[old]:return None,'partial_rename',[]
        for text in (source,donor,target):
            if any(any(term in token for term in [old,new]+aliases) for token in re.findall(r'<[^>]*>|\[[^\]]*\]',text)):return None,'markup_hold',[]
        if len(list(alias_pattern(aliases).finditer(donor)))!=counts[old]:return None,'name_count_hold',[]
        for alias in aliases:
            if alias in replacement and replacement[alias]!=translated:return None,'alias_conflict',[]
            replacement[alias]=translated
        if (old,new) not in [(c['from_en'],c['to_en']) for c in used]:used.append({'from_en':old,'to_en':new,'to_ko':translated})
    pattern=alias_pattern(replacement);pieces=[];cursor=0;edits=[]
    for match in pattern.finditer(donor):
        pieces.append(donor[cursor:match.start()]);name=replacement[match[0]];pieces.append(name);cursor=match.end()
        particle=re.match(r'(으로|로|은|는|이|가|을|를|과|와)(?=$|[^가-힣A-Za-z0-9_])',donor[cursor:])
        if particle:
            fixed=repair_particle(name,particle[0]);pieces.append(fixed);cursor+=len(particle[0])
            if fixed!=particle[0]:edits.append({'from':match[0]+particle[0],'to':name+fixed})
    pieces.append(donor[cursor:]);candidate=''.join(pieces)
    try:check_translation(target,candidate)
    except ValueError:return None,'candidate_structure_hold',[]
    return candidate,'name_adapted',used+[{'particle_edits':edits}]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--game',type=Path,required=True)
    ap.add_argument('--comparison-dir',type=Path,required=True);ap.add_argument('--package',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True);args=ap.parse_args()
    for protected in (args.game,args.package,args.comparison_dir):
        if args.output_dir.resolve().is_relative_to(protected.resolve()) or protected.resolve().is_relative_to(args.output_dir.resolve()):
            raise ValueError('Build output must be separate from game, package and comparison inputs')
    if args.output_dir.exists():raise SystemExit('Output exists; choose a fresh directory')
    manifest=json.loads((args.package/'manifest.json').read_text(encoding='utf-8'))
    reference=json.loads((args.comparison_dir/'manifest.json').read_text(encoding='utf-8'))
    comparison=args.comparison_dir/reference['comparison_file']
    if file_digest(comparison)!=reference['comparison_sha256']:raise ValueError('Comparison snapshot changed')
    rows={};counts=Counter();decisions=[]
    with gzip.open(comparison,'rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line)
            if r['current_round_excluded']:counts['current_round_preserved']+=1;continue
            if r['vanilla_en'] is None:counts['no_reference']+=1;continue
            value,status,detail=adapted_translation(r['vanilla_en'],r['vanilla_ko'],r['genesis_en'])
            counts[status]+=1
            if value is not None:
                target='mods/'+r['provider']+'/strings/'+r['file'];key=(target.lower(),r['string_id'])
                if key in rows:raise ValueError('Duplicate donor location')
                rows[key]=(r['genesis_en'],value,status)
                if status=='name_adapted':decisions.append({'target':target,'string_id':r['string_id'],'source_en':r['genesis_en'],'donor_ko':r['vanilla_ko'],'translation_ko':value,'changes':detail,'validation':'exact_english_template_and_structural_rules','human_reviewed':False})
    # Build everything outside the game/released package first.
    args.output_dir.mkdir(parents=True);output=args.output_dir/'installer-data';shutil.copytree(args.package,output)
    operations=[];total=Counter();used=set();backups=list((args.game/'.genesis-kr-backups').glob('*/originals'))
    for operation in manifest['operations']:
        op=dict(operation)
        if op['kind']!='text_recipe':operations.append(op);continue
        recipe=json.loads(gzip.decompress((args.package/'blobs'/op['blob']).read_bytes()))
        if recipe['kind']=='plugin':operations.append(op);continue
        original=None
        for root in backups+[args.game]:
            path=root/op['target']
            if path.is_file():
                raw=path.read_bytes()
                if sha(raw)==op['input_sha256']:original=raw;break
        if original is None:raise ValueError('Hash-matching original missing: '+op['target'])
        mapping={sid:tuple(values) for sid,values in recipe['translations']}
        before,_=patch_strings(original,recipe['kind'],mapping)
        if sha(before)!=op['output_sha256']:raise ValueError('Released recipe output mismatch')
        original_text={sid:text for sid,text,_ in read_strings(original,recipe['kind'])}
        edits=Counter()
        for (target,sid),(expected,value,status) in rows.items():
            if target!=op['target'].lower():continue
            if original_text.get(sid)!=expected:raise ValueError('Original Genesis source mismatch')
            used.add((target,sid))
            if mapping.get(sid,(expected,expected))[1]!=value:edits[status]+=1
            mapping[sid]=(expected,value)
        after,changed=patch_strings(original,recipe['kind'],mapping)
        total.update(edits)
        if after!=before:
            blob=gzip.compress(json.dumps({'kind':recipe['kind'],'translations':sorted(mapping.items())},ensure_ascii=False,separators=(',',':')).encode(),mtime=0)
            blob_id=sha(blob);(output/'blobs'/blob_id).write_bytes(blob)
            old_text={sid:text for sid,text,_ in read_strings(before,recipe['kind'])}
            new_text={sid:text for sid,text,_ in read_strings(after,recipe['kind'])}
            upgrade={sid:(old_text[sid],text) for sid,text in new_text.items() if old_text[sid]!=text}
            upgraded,_=patch_strings(before,recipe['kind'],upgrade)
            if upgraded!=after:raise ValueError('Upgrade output differs from clean installation')
            upgrade_blob=gzip.compress(json.dumps({'kind':recipe['kind'],'translations':sorted(upgrade.items())},ensure_ascii=False,separators=(',',':')).encode(),mtime=0)
            upgrade_id=sha(upgrade_blob);(output/'blobs'/upgrade_id).write_bytes(upgrade_blob)
            op.update(blob=blob_id,output_sha256=sha(after),text_changes=len(changed),upgrade_from=[{'input_sha256':sha(before),'blob':upgrade_id}])
            staged=args.output_dir/'preview'/op['target'];staged.parent.mkdir(parents=True,exist_ok=True);staged.write_bytes(after)
            total['updated_strings_files']+=1
        operations.append(op)
    if used!=set(rows):raise ValueError('Donor locations missing from package operations')
    manifest.update(operations=operations,release_state='TEST_BUILD',in_game_verified=False,
                    donor_reuse={'comparison_sha256':reference['comparison_sha256'],'selection_counts':dict(counts),'actual_recipe_changes':dict(total),'existing_donor_quality_review':'out_of_scope','current_round_translations_preserved':True})
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (args.output_dir/'name-adaptations.json').write_text(json.dumps({'items':decisions},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report={'selection_counts':dict(counts),'actual_recipe_changes':dict(total),'name_adaptation_locations':len(decisions),'source_comparison_sha256':reference['comparison_sha256'],'game_modified':False,'clean_and_upgrade_outputs_identical':True}
    (args.output_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
