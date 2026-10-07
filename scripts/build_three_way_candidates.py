"""Read-only three-way Strings comparison; proposals never modify installed files."""
import argparse, csv, difflib, gzip, hashlib, json, re, struct, sys, zlib
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patch_engine import read_strings, check_translation

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def file_digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

# Observed English pairs, not global lore replacements. Every non-term byte must match.
RULES = [
    ('Neon', 'Nar Shaddaa', ['네온'], '나르 샤다'),
    ('New Atlantis', 'Coruscant', ['뉴 아틀란티스', '뉴아틀란티스'], '코러산트'),
    ('UC', 'Empire', ['식민지 연합', '식민지연합', 'UC'], '제국'),
    ('UC', 'Imperial', ['식민지 연합', '식민지연합', 'UC'], '제국'),
    ('United Colonies', 'Galactic Empire', ['식민지 연합', '식민지연합', 'UC'], '은하 제국'),
    ('United Colonies', 'Empire', ['식민지 연합', '식민지연합', 'UC'], '제국'),
    ('Aurora', 'Spice', ['오로라'], '스파이스'),
    ('Vasco', 'ND-5', ['바스코'], 'ND-5'),
    ('Mars', 'Geonosis', ['화성', '마스'], '지오노시스'),
    ("House Va'ruun", 'Sith', ['바룬 가문', '바룬 가문', '바룬'], '시스'),
    ("Va'ruun", 'Sith', ['바룬'], '시스'),
    ('Ecliptic', 'Trandoshan', ['이클립틱', '이클립티크'], '트랜도샨'),
    ('Ecliptic', 'Trandoshans', ['이클립틱', '이클립티크'], '트랜도샨'),
]
OLD_PATTERN = re.compile(r'(?<![A-Za-z0-9_])(?:'+ '|'.join(re.escape(s) for s in sorted({r[0] for r in RULES}, key=len, reverse=True)) +r')(?![A-Za-z0-9_])')

def alias_pattern(aliases):
    # Hold compounds (e.g. 마스터 is not 마스) and embedded Latin acronyms.
    terms = '|'.join(re.escape(a) for a in sorted(set(aliases),key=len,reverse=True))
    return re.compile(r'(?<![가-힣A-Za-z0-9_])(?:'+terms+r')(?=$|[^가-힣A-Za-z0-9_]|(?:에서|에게|부터|까지|으로|은|는|이|가|을|를|과|와|의|에|께|도|만|로)(?:$|[^가-힣A-Za-z0-9_]))')

def name_changes(source, target):
    matches = list(OLD_PATTERN.finditer(source))
    states = [(0, [])]; cursor = 0
    for match in matches:
        gap = source[cursor:match.start()]; updated = []
        options = [(match[0], None)] + [(r[1],r) for r in RULES if r[0] == match[0]]
        for pos, changes in states:
            if not target.startswith(gap,pos): continue
            pos += len(gap)
            for text, rule in options:
                if target.startswith(text,pos): updated.append((pos+len(text),changes+([rule] if rule else [])))
        states = updated; cursor = match.end()
        if len(states)>256: return None
    solutions = [c for p,c in states if target[p:] == source[cursor:] and c]
    return solutions[0] if len(solutions)==1 else None

def propose(source, donor, target):
    if not donor or not re.search('[가-힣]', donor) or '\ufffd' in donor:
        return None, 'donor_not_korean_or_invalid', []
    try: check_translation(source, donor)
    except ValueError as exc: return None, 'donor_structure: '+str(exc), []
    if source == target: return donor, 'reuse_candidate', []
    changes = name_changes(source, target)
    if not changes: return None, 'other_english_changes', []
    # Never replace terms embedded in markup. Control/tag contents are immutable here.
    for text in (source,target,donor):
        if any(any(any(term in token for term in [old,new]+aliases) for old,new,aliases,_ in changes) for token in re.findall(r'<[^>]*>|\[[^\]]*\]',text)):
            return None, 'term_inside_markup', []
    replacement = {}; used = []; english_counts = Counter(r[0] for r in changes)
    for old, new, aliases, translated in changes:
        if any(r[0] == old and r[3] != translated for r in changes):
            return None, 'conflicting_term_targets', []
        if len(list(re.finditer(r'(?<![A-Za-z0-9_])'+re.escape(old)+r'(?![A-Za-z0-9_])',source))) != english_counts[old]:
            return None, 'partially_changed_term', []
        for alias in aliases:
            if alias in replacement and replacement[alias] != translated: return None, 'overlapping_aliases', []
            replacement[alias] = translated
        if (old,new) not in [(r['from_en'],r['to_en']) for r in used]:
            pattern = alias_pattern(aliases)
            hits = list(pattern.finditer(donor))
            if len(hits) != english_counts[old]: return None, 'korean_term_count_mismatch', []
            used.append({'from_en':old,'to_en':new,'to_ko':translated,'occurrences':len(hits)})
    pattern = alias_pattern(replacement)
    # Keep adjacent particles unchanged: attachment/loanword pronunciation needs human review.
    candidate = pattern.sub(lambda m: replacement[m[0]], donor)
    try: check_translation(target,candidate)
    except ValueError as exc: return None, 'candidate_structure: '+str(exc), []
    return candidate, 'term_swap_candidate', used

def references(data):
    english, korean, provenance = {}, {}, []
    for archive in sorted(data.glob('*.ba2')):
        found=[]
        with archive.open('rb') as f:
            header=f.read(32)
            if len(header)<24: continue
            magic, version, kind, count, offset = struct.unpack_from('<4sI4sIQ', header)
            if magic!=b'BTDX' or kind!=b'GNRL':continue
            f.seek(offset);names=[]
            for _ in range(count):
                size=struct.unpack('<H',f.read(2))[0];names.append(f.read(size).decode('utf-8'))
            for index,name in enumerate(names):
                filename = Path(name.replace('\\', '/')).name.lower();suffix = Path(filename).suffix
                if '_en.' not in filename or suffix not in ('.strings', '.dlstrings', '.ilstrings'):continue
                if version!=2:raise ValueError('Unsupported English archive: '+archive.name)
                f.seek(32+index*36);rec=struct.unpack('<I4sIIQIII',f.read(36))
                f.seek(rec[4]);payload=f.read(rec[5] or rec[6])
                if rec[5]: payload = zlib.decompress(payload)
                if len(payload) != rec[6]: raise ValueError('Archive entry size mismatch')
                if filename in english: raise ValueError('Duplicate reference file: ' + filename)
                english[filename] = {sid: text for sid, text, _ in read_strings(payload, suffix)};found.append(filename)
        if found:provenance.append({'file':archive.name,'sha256':file_digest(archive),'role':'vanilla_english','english_files':found})
    for path in sorted((data/'Strings').glob('*')):
        filename = path.name.lower(); suffix = path.suffix.lower()
        if '_en.' not in filename or suffix not in ('.strings','.dlstrings','.ilstrings'): continue
        raw = path.read_bytes()
        korean[filename] = {sid: text for sid, text, _ in read_strings(raw, suffix)}
        provenance.append({'file': 'Strings/'+path.name, 'sha256': digest(raw), 'role': 'existing_korean'})
    return english, korean, provenance

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-data', type=Path, required=True)
    ap.add_argument('--audit-dir', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--inspect', action='store_true')
    args = ap.parse_args()
    en, ko, provenance = references(args.base_data)
    rows = []; counts = Counter(); diffs = Counter(); examples = {}
    source = args.audit_dir/'strings_comparison.csv'
    with source.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            name = row['file'].replace('\\','/').lower()
            if name.count('/') != 1: continue
            filename = Path(name).name; sid = int(row['string_id'], 0)
            vanilla = en.get(filename, {}).get(sid)
            donor = ko.get(filename, {}).get(sid)
            genesis = row['source']
            status = 'missing_vanilla_reference' if vanilla is None else 'missing_korean_reference' if donor is None else 'unchanged' if vanilla == genesis else 'changed'
            counts[status] += 1
            if status == 'changed' and args.inspect:
                ops = [(vanilla[a:b], genesis[c:d]) for tag,a,b,c,d in difflib.SequenceMatcher(None, vanilla, genesis, autojunk=False).get_opcodes() if tag != 'equal']
                if len(ops) == 1:
                    diffs[ops[0]] += 1
                    if max(len(vanilla),len(genesis)) < 180: examples.setdefault(ops[0], (vanilla,donor,genesis))
            rows.append({'file': filename, 'provider': row['mod'], 'string_id': sid, 'vanilla_en': vanilla, 'vanilla_ko': donor, 'genesis_en': genesis, 'comparison': status})
    if args.inspect:
        print(json.dumps({'counts': dict(counts), 'korean_quality':dict(Counter('replacement_character' if '\ufffd' in r['vanilla_ko'] else 'hangul' if re.search('[가-힣]', r['vanilla_ko']) else 'no_hangul' for r in rows if r['vanilla_ko'] is not None)), 'samples':rows[10:13], 'diffs': [{'change':p,'count':n,'example':examples.get(p)} for p,n in diffs.most_common(8)]}, ensure_ascii=True, indent=2)); return
    out = args.output_dir
    if out.exists(): raise SystemExit('Output exists; preserve review edits and choose a fresh directory.')
    out.mkdir(parents=True)
    exclusions = set()
    for name in ('translation_candidates.csv','semantic_review_suggestions.csv','final_review_suggestions.csv'):
        with (args.audit_dir/name).open(encoding='utf-8-sig',newline='') as f:
            exclusions.update(r['source'] for r in csv.DictReader(f))
        provenance.append({'file':name,'sha256':file_digest(args.audit_dir/name),'role':'current_round_exclusions'})
    provenance.append({'file':'strings_comparison.csv','sha256':digest(source.read_bytes()),'role':'original_genesis_english_audit'})
    proposal_counts = Counter(); files = Counter(); candidate_examples = []; review = []; seen = set()
    output = out/'comparison.jsonl.gz'
    with output.open('wb') as rawout, gzip.GzipFile(fileobj=rawout,mode='wb',mtime=0,filename='') as compressed:
        for row in rows:
            key = (row['provider'],row['file'],row['string_id'])
            if key in seen: raise ValueError('Duplicate original Genesis location')
            seen.add(key)
            candidate, status, used = (None,row['comparison'],[]) if row['vanilla_en'] is None or row['vanilla_ko'] is None else propose(row['vanilla_en'],row['vanilla_ko'],row['genesis_en'])
            excluded = row['genesis_en'] in exclusions
            row.update(candidate_ko=candidate, reuse_status=status, term_changes=used,
                       current_round_excluded=excluded, review_status='pending', human_reviewed=False,
                       review_flags=['donor_quality_unreviewed']+(['particles_and_context_need_review'] if status=='term_swap_candidate' else []))
            proposal_counts[status] += 1; files[row['file']] += 1
            compressed.write((json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8'))
            if status=='term_swap_candidate' and not excluded:
                review.append(row)
                if len(candidate_examples)<10 and len(row['genesis_en'])<160: candidate_examples.append(row)
    batches=[]
    for start in range(0,len(review),250):
        path=out/f'term-candidates-{start//250+1:04}.json'
        path.write_text(json.dumps({'schema_version':1,'items':review[start:start+250]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        batches.append({'file':path.name,'items':len(review[start:start+250]),'sha256':digest(path.read_bytes())})
    manifest={'schema_version':1,'counts_unit':'StringID locations, not unique sentences',
              'genesis_version':'8.8.32 (original pre-patch audit)', 'comparison_counts':dict(counts),
              'reuse_counts':dict(proposal_counts),'files':dict(files),'source_provenance':provenance,
              'rules':[{'from_en':a,'to_en':b,'korean_aliases':c,'to_ko':d} for a,b,c,d in RULES],
              'comparison_file':output.name,'comparison_sha256':digest(output.read_bytes()),
              'term_review_items':len(review),'review_batches':batches,
              'notes':['All proposals require review; no game or released installer data was changed.',
                       'Full comparison includes current-round sources for reference; term review batches exclude them.',
                       'Same file/StringID does not prove cross-version semantic identity; unchanged English is required for reuse.',
                       'Particles are preserved and explicitly flagged for human review.',
                       'Any missing reference is held even when an existing Korean donor exists.'],
              'examples':candidate_examples}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'comparison_counts':dict(counts),'reuse_counts':dict(proposal_counts),'term_review_items':len(review),'output_bytes':output.stat().st_size}))

if __name__ == '__main__': main()
