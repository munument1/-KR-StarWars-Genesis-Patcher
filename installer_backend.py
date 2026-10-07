"""Guarded generation and transactional backup/apply/restore for the local patcher."""
import base64,gzip,hashlib,json,os,re,subprocess,uuid
from pathlib import Path
from patch_engine import patch_plugin,patch_strings
from preserve_font_resources import patch_font_bytes
from hud_layout import patch_hud

class InstallError(ValueError):pass
def sha(raw):return hashlib.sha256(raw).hexdigest()
def safe(root,relative):
    root=Path(root).resolve();p=(root/relative).resolve()
    if not p.is_relative_to(root) or p==root:raise InstallError('Path outside selected folder')
    return p
def atomic(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()
def save(path,value):atomic(path,json.dumps(value,ensure_ascii=False,indent=2).encode())
def check_game_closed():
    if os.name=='nt':
        output=subprocess.run(['tasklist','/FI','IMAGENAME eq Starfield.exe','/FO','CSV','/NH'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,check=True).stdout.lower()
        if b'"starfield.exe"' in output:raise InstallError('Starfield를 종료한 뒤 적용 또는 복원해 주세요.')
def check_base_content(game,manifest,progress):
    checks=manifest.get('base_content_checks',[])
    if not checks:return {}
    ini=game/'ModOrganizer.ini'
    match=re.search(r'^gamePath\s*=\s*@ByteArray\((.*)\)\s*$',ini.read_text(encoding='utf-8-sig'),re.M)
    if not match:raise InstallError('Could not locate the Starfield folder in ModOrganizer.ini')
    data=Path(match.group(1).replace('\\\\','\\'))/'Data';available={}
    for r in checks:
        p=data/r['name'];available[r['name'].lower()]=p.exists()
        if not p.exists():
            if r['required']:raise InstallError(f'Required game content missing: {r["name"]}')
            continue
        progress('기본 게임·DLC 파일 확인: '+r['name']);h=hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        if h.hexdigest()!=r['sha256']:raise InstallError(f'Base game/DLC version differs from this test build: {r["name"]}')
    return available

def providers(game,profile):
    path=safe(game,f'profiles/{profile}/modlist.txt')
    if not path.is_file():raise InstallError('Selected MO2 profile not found')
    names=[s[1:] for s in path.read_text(encoding='utf-8-sig').splitlines() if s.startswith('+')]
    result={}
    return names,result
def winner(game,names,target):
    parts=Path(target).parts
    if len(parts)<3 or parts[0]!='mods':return None
    relative=Path(*parts[2:])
    for name in names:
        if safe(game,Path('mods')/name/relative).is_file():return name
    return None

def generate(game,package,stage,profile=None,progress=lambda text:None):
    game=Path(game).resolve();package=Path(package).resolve();stage=Path(stage).resolve()
    if stage.is_relative_to(game) or game.is_relative_to(stage):raise InstallError('Preview folder must be separate from the game folder')
    if stage.is_relative_to(package) or package.is_relative_to(stage):raise InstallError('Preview folder must be separate from the package folder')
    manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8'))
    content=check_base_content(game,manifest,progress)
    names,_=providers(game,profile or manifest['default_profile']);items=[]
    for index,operation in enumerate(manifest['operations'],1):
        r=dict(operation);target=safe(game,r['target']);current=target.read_bytes() if target.exists() else None
        if r.get('base_plugin') and not content.get(r['base_plugin'].lower(),True):
            r['status']='content_not_installed';items.append(r);continue
        actual=sha(current) if current is not None else None
        if r['target'].startswith('mods/') and Path(r['target']).parts[1] not in names:
            raise InstallError(f'Required mod is disabled or missing: {Path(r["target"]).parts[1]}')
        if actual==r['output_sha256']:
            r['status']='already_applied';r['current_sha256']=actual;items.append(r);continue
        provider=winner(game,names,r['target'])
        if r['kind']=='fallback_strings' and provider is not None:
            r['status']='provided_by_enabled_mod';r['provider']=provider;items.append(r);continue
        if r['target'].startswith('mods/') and r['kind']!='fallback_strings' and provider!=Path(r['target']).parts[1]:
            raise InstallError(f'Enabled mod priority differs: {r["target"]}')
        if actual!=r['input_sha256']:raise InstallError(f'Unsupported or changed input: {r["target"]}')
        blob=safe(package,'blobs/'+r['blob']).read_bytes()
        if sha(blob)!=r['blob']:raise InstallError('Package blob checksum failed')
        if r['kind']=='text_recipe':
            recipe=json.loads(gzip.decompress(blob));mapping={tuple(k) if isinstance(k,list) else k:tuple(v) for k,v in recipe['translations']}
            output,_=patch_plugin(current,mapping) if recipe['kind']=='plugin' else patch_strings(current,recipe['kind'],mapping)
        elif r['kind']=='font_recipe':
            values=json.loads(gzip.decompress(blob));additions={int(fid):{int(c):{k:base64.b64decode(v) for k,v in g.items()} for c,g in glyphs.items()} for fid,glyphs in values.items()}
            output,_=patch_font_bytes(current,additions)
        elif r['kind']=='hud_recipe':output=patch_hud(current,json.loads(gzip.decompress(blob)))
        else:output=blob
        if sha(output)!=r['output_sha256']:raise InstallError(f'Generated output checksum failed: {r["target"]}')
        path=safe(stage,r['target']);atomic(path,output)
        r.update(status='prepared',current_sha256=actual,staged_relative=r['target']);items.append(r)
        progress(f'{index}/{len(manifest["operations"])}  {Path(r["target"]).name}')
    report={'game':str(game),'profile':profile or manifest['default_profile'],'package_manifest_sha256':sha((package/'manifest.json').read_bytes()),'base_content_checks':manifest.get('base_content_checks',[]),'operations':items,'state':'prepared','installed':False}
    save(stage/'prepared.json',report);return report

def apply(stage,progress=lambda text:None):
    check_game_closed()
    stage=Path(stage).resolve();prepared=json.loads((stage/'prepared.json').read_text(encoding='utf-8'));game=Path(prepared['game'])
    check_base_content(game,prepared,progress)
    entries=[r for r in prepared['operations'] if r['status']=='prepared']
    if not entries:raise InstallError('No pending changes')
    names,_=providers(game,prepared['profile'])
    for r in entries:
        p=safe(game,r['target']);actual=sha(p.read_bytes()) if p.exists() else None
        if actual!=r['current_sha256']:raise InstallError(f'Input changed after preparation: {r["target"]}')
        provider=winner(game,names,r['target'])
        if r['target'].startswith('mods/'):
            if r['kind']=='fallback_strings' and provider is not None:raise InstallError('Fallback now conflicts with an enabled mod')
            if r['kind']!='fallback_strings' and provider!=Path(r['target']).parts[1]:raise InstallError('Mod priority changed after preparation')
        if sha(safe(stage,r['staged_relative']).read_bytes())!=r['output_sha256']:raise InstallError('Staged file changed')
    backup=safe(game,Path('.genesis-kr-backups')/uuid.uuid4().hex);backup.mkdir(parents=True)
    journal={'game':str(game),'state':'backup_in_progress','entries':entries}
    for r in entries:
        original=safe(game,r['target'])
        if original.exists():
            raw=original.read_bytes()
            if sha(raw)!=r['current_sha256']:raise InstallError('Input changed while backing up')
            atomic(safe(backup,Path('originals')/r['target']),raw)
    journal['state']='applying';save(backup/'journal.json',journal)
    try:
        for i,r in enumerate(entries,1):
            current=safe(game,r['target'])
            if (sha(current.read_bytes()) if current.exists() else None)!=r['current_sha256']:
                raise InstallError('Input changed during installation')
            atomic(safe(game,r['target']),safe(stage,r['staged_relative']).read_bytes())
            progress(f'{i}/{len(entries)}  {Path(r["target"]).name}')
        journal['state']='applied';save(backup/'journal.json',journal)
    except Exception:
        restore(backup,allow_original=True);raise
    return backup

def restore(backup,allow_original=False,progress=lambda text:None):
    check_game_closed()
    backup=Path(backup).resolve();journal=json.loads((backup/'journal.json').read_text(encoding='utf-8'));game=Path(journal['game']).resolve()
    if not backup.is_relative_to(game/'.genesis-kr-backups'):raise InstallError('Backup is outside its recorded game folder')
    for r in journal['entries']:
        target=safe(game,r['target']);actual=sha(target.read_bytes()) if target.exists() else None
        allowed={r['output_sha256'],r['current_sha256']}
        if actual not in allowed:raise InstallError(f'File changed since installation: {r["target"]}')
        if r['current_sha256'] is not None:
            if sha(safe(backup,Path('originals')/r['target']).read_bytes())!=r['current_sha256']:raise InstallError('Backup checksum failed')
    journal['state']='restoring';save(backup/'journal.json',journal)
    for i,r in enumerate(journal['entries'],1):
        target=safe(game,r['target'])
        if r['current_sha256'] is None:
            if target.exists():target.unlink()
        else:atomic(target,safe(backup,Path('originals')/r['target']).read_bytes())
        progress(f'{i}/{len(journal["entries"])}  {Path(r["target"]).name}')
    journal['state']='restored';save(backup/'journal.json',journal);return journal
