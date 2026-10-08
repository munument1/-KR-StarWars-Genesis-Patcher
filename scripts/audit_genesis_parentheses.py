"""Audit bilingual parentheses in Genesis patcher translations without modifying recipes.

Usage: python scripts/audit_genesis_parentheses.py --repo . --out parentheses-review.csv
       python scripts/audit_genesis_parentheses.py --repo . --out full-review.csv --include-legacy
       python scripts/audit_genesis_parentheses.py --self-test
"""
import argparse
import csv
import gzip
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

HANGUL = re.compile(r'[가-힣]')
LATIN = re.compile(r'[A-Za-z]')
PARENS = re.compile(r'\(([^()\r\n]{1,100})\)')
EN_SUFFIX = re.compile(r"([A-Za-z][\w'’./-]*(?:\s+[A-Za-z][\w'’./-]*){0,5})\s*$")
KO_SUFFIX = re.compile(r"([가-힣][가-힣·'’-]*(?:\s+[가-힣][가-힣·'’-]*){0,5})\s*$")
CODE = re.compile(r'(?:[A-Z]{2,}[0-9/-]*|[A-Z]{1,5}[-_]\d+[A-Za-z0-9/-]*)$')
EXPLANATIONS = re.compile(r'^(?:요약|설명|참고|주의|버그 신고|작업 중|출시 예정|구|신|씨앗|동체|가죽|줄기|분비선|소형 포트)$')


def candidates(translation, source):
    """Yield review candidates, never assume semantic equivalence."""
    for m in PARENS.finditer(translation):
        inside = m.group(1).strip()
        left = translation[max(0, m.start() - 95):m.start()]
        if not left or '<' in inside or '>' in inside or '\\' in inside:
            continue
        if HANGUL.search(inside) and not LATIN.search(inside):
            last = EN_SUFFIX.search(left)
            if not last:
                continue
            original = last.group(1).strip()
            if CODE.fullmatch(original.split()[-1]) or EXPLANATIONS.fullmatch(inside):
                continue
            direction = 'English(Korean)'
        elif LATIN.search(inside) and not HANGUL.search(inside):
            last = KO_SUFFIX.search(left)
            if not last:
                continue
            original = last.group(1).strip()
            if CODE.fullmatch(inside) or len(inside) <= 1:
                continue
            direction = 'Korean(English)'
        else:
            continue
        yield {'direction': direction, 'left_context': original, 'parenthetical': inside,
               'english_occurs_in_source': inside.casefold() in source.casefold() if direction == 'Korean(English)' else original.casefold() in source.casefold(),
               'preview': translation[max(0, m.start() - 48):min(len(translation), m.end() + 48)]}


def active_rows(repo):
    base = repo / 'installer-data'
    manifest = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
    seen = set()
    for op in manifest['operations']:
        if op['kind'] != 'text_recipe' or op['blob'] in seen:
            continue
        seen.add(op['blob'])
        path = base / 'blobs' / op['blob']
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != op['blob']:
            raise ValueError('Recipe blob checksum mismatch: ' + str(path))
        recipe = json.loads(gzip.decompress(payload))
        for key, pair in recipe['translations']:
            if len(pair) >= 2:
                yield ('active', op['target'], json.dumps(key, ensure_ascii=False), pair[0], pair[1])


def legacy_rows(repo):
    base = repo / 'translation-review' / 'legacy'
    manifest = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
    for batch in manifest['batches']:
        records = json.loads((base / batch['path']).read_text(encoding='utf-8'))['items']
        for entry in records:
            yield ('legacy', batch['path'], entry['id'], entry['source_en'], entry['current_patch_ko'])


def audit(rows, csv_path):
    counts = Counter()
    with csv_path.open('w', encoding='utf-8-sig', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=('scope', 'file', 'key', 'direction', 'left_context', 'parenthetical', 'english_occurs_in_source', 'preview'))
        writer.writeheader()
        for scope, file, key, source, translation in rows:
            counts['records_scanned'] += 1
            for candidate in candidates(translation, source):
                writer.writerow({'scope': scope, 'file': file, 'key': key, **candidate})
                counts['candidates'] += 1
                counts[candidate['direction']] += 1
    return counts


def self_test():
    checks = [
        ('헤이드리안(Hadrian)', 'Hadrian', 'Korean(English)'),
        ('Dantooine(단투인)', 'Dantooine', 'English(Korean)'),
        ('단투인(Dantooine)', 'Dantooine', 'Korean(English)'),
        ('번역(요약)', 'Translation', None),
        ('CAPS(완전 자동 조종 시스템)', 'CAPS', None),
        ('A-280 (버그 신고)', 'A-280 (report this as a bug)', None),
        ('은하 뉴스 네트워크(GNN)', 'Galactic News Network (GNN)', None),
        ('X-윙 (S) 원자로 (C)', 'X-wing (S) Reactor (C)', None),
        ('우주 너머 (<Alias=Planet>)', 'From Beyond (<Alias=Planet>)', None),
    ]
    for translation, source, expected in checks:
        got = [c['direction'] for c in candidates(translation, source)]
        assert got == ([] if expected is None else [expected]), (translation, got)
    print(f'PASS: {len(checks)} candidate/exclusion tests')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--out', type=Path)
    parser.add_argument('--include-legacy', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.out:
        parser.error('--out CSV path is required')
    import itertools
    rows = active_rows(args.repo)
    if args.include_legacy:
        rows = itertools.chain(rows, legacy_rows(args.repo))
    result = audit(rows, args.out)
    print(json.dumps(dict(result), ensure_ascii=False))
    print('Review CSV written:', args.out)
    print('No installer-data files, hashes, or existing translations were modified.')


if __name__ == '__main__':
    main()
