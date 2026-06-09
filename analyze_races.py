import json
import os
import sys

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

outdir = 'C:/Users/unoen/projects/k-bar-ai/race_check_results'

race_ids = [
    '202610011101','202609010301','202606020101',
    '202610011102','202609010302','202606020102',
    '202609010303','202610011103','202606020103',
    '202609010304','202610011104','202606020104',
    '202609010305','202610011105','202606020105',
    '202606020106','202609010306','202610011106',
    '202609010307','202606020107','202610011107',
    '202609010308','202610011108','202606020108',
    '202606020109','202609010309','202610011109',
    '202606020110','202609010310','202610011110',
    '202609010311','202606020111','202610011111',
    '202609010312','202610011112','202606020112',
]

print('=' * 130)
print('  Race Data Integrity Check - All 36 Races')
print('=' * 130)
print()

header = f"{'RACE_ID':<14} {'VENUE':<6} {'R#':<4} {'RACE_NAME':<20} {'ENTRIES':<8} {'HEAD':<6} {'NULL_POST':<10} {'NULL_BKT':<10} {'NULL_JKY':<10} {'ISSUES'}"
print(header)
print('-' * 130)

total_issues = 0
races_with_issues = 0
all_details = []

for race_id in race_ids:
    fpath = os.path.join(outdir, f'{race_id}.json')
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f'{race_id:<14} ERROR: {e}')
        continue

    race_name = data.get('race_name', 'N/A')
    venue = data.get('racecourse_name', '?')
    race_num = data.get('race_number', '?')
    head_count = data.get('head_count')
    entries = data.get('entries', [])
    entry_count = len(entries)

    null_post = []
    null_bracket = []
    null_jockey = []

    for e in entries:
        horse = e.get('horse', {}) or {}
        horse_name = horse.get('name', '???')

        if e.get('post_position') is None:
            null_post.append(horse_name)
        if e.get('bracket_number') is None:
            null_bracket.append(horse_name)
        jockey = e.get('jockey')
        if jockey is None or (isinstance(jockey, dict) and jockey.get('name') is None):
            null_jockey.append(horse_name)

    issues = []
    if null_post:
        issues.append(f'post({len(null_post)})')
    if null_bracket:
        issues.append(f'bracket({len(null_bracket)})')
    if null_jockey:
        issues.append(f'jockey({len(null_jockey)})')
    if head_count is not None and entry_count != head_count:
        issues.append(f'count_mismatch(entries={entry_count},head={head_count})')

    issue_str = ', '.join(issues) if issues else 'OK'
    has_issue = len(issues) > 0

    if has_issue:
        races_with_issues += 1
        total_issues += len(null_post) + len(null_bracket) + len(null_jockey)

    print(f'{race_id:<14} {venue:<6} {str(race_num):<4} {race_name:<20} {entry_count:<8} {str(head_count):<6} {len(null_post):<10} {len(null_bracket):<10} {len(null_jockey):<10} {issue_str}')

    if has_issue:
        detail = {
            'race_id': race_id, 'venue': venue, 'race_num': race_num, 'race_name': race_name,
            'null_post': null_post, 'null_bracket': null_bracket, 'null_jockey': null_jockey,
            'entry_count': entry_count, 'head_count': head_count
        }
        all_details.append(detail)

print()
print('=' * 130)
print(f'  SUMMARY: {len(race_ids)} races checked | {races_with_issues} races with issues | {total_issues} total null fields')
print('=' * 130)

# Print details for races with issues
if all_details:
    print()
    print('DETAILED BREAKDOWN OF PROBLEMATIC RACES:')
    print('=' * 90)
    for d in all_details:
        print(f"\n--- {d['race_id']} | {d['venue']}{d['race_num']}R {d['race_name']} (entries={d['entry_count']}, head_count={d['head_count']}) ---")
        if d['null_post']:
            print(f"  post_position=null: {', '.join(d['null_post'])}")
        if d['null_bracket']:
            print(f"  bracket_number=null: {', '.join(d['null_bracket'])}")
        if d['null_jockey']:
            print(f"  jockey=null: {', '.join(d['null_jockey'])}")

# Ocean S full entry list
print()
print('=' * 130)
print('  OCEAN S (202606020111) - Full Entry Details')
print('=' * 130)
ocean_path = os.path.join(outdir, '202606020111.json')
with open(ocean_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Race: {data.get('race_name')} | Venue: {data.get('racecourse_name')} | R{data.get('race_number')}")
print(f"Surface: {data.get('surface')} {data.get('distance_m')}m | Direction: {data.get('direction')}")
print(f"Head count: {data.get('head_count')} | Actual entries: {len(data.get('entries', []))}")
print()

entries = data.get('entries', [])
# Sort by post_position (nulls last)
entries_sorted = sorted(entries, key=lambda e: (e.get('post_position') is None, e.get('post_position') or 999))

print(f"{'Post':<8} {'Bracket':<9} {'Horse':<22} {'Jockey':<14} {'Wt(kg)':<8} {'Odds':<8} {'Fav':<5} {'Age':<5} {'Sex'}")
print('-' * 110)
for e in entries_sorted:
    post = e.get('post_position')
    post_str = str(post) if post is not None else '**NULL**'
    bracket = e.get('bracket_number')
    bracket_str = str(bracket) if bracket is not None else '**NULL**'
    horse = e.get('horse', {}) or {}
    horse_name = horse.get('name', 'NULL')
    horse_sex = horse.get('sex', '?')
    jockey = e.get('jockey')
    if jockey and isinstance(jockey, dict):
        jockey_name = jockey.get('name', 'NULL')
    else:
        jockey_name = '**NULL**'
    weight = e.get('weight_carried_kg', 'NULL')
    odds = e.get('win_odds', 'NULL')
    fav = e.get('win_favorite', 'NULL')
    age = e.get('horse_age', '?')

    print(f"{post_str:<8} {bracket_str:<9} {horse_name:<22} {jockey_name:<14} {str(weight):<8} {str(odds):<8} {str(fav):<5} {str(age):<5} {horse_sex}")

print()
print('(Fields marked with **NULL** are missing/null)')
print()
print('Done.')
