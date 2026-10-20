"""Audit original inputs without rewriting timings, positions, or collision rules."""
import argparse
import hashlib
import json
from pathlib import Path

import blast_processing as b
import original_replays
from level_catalog import entries

ROOT=Path(__file__).resolve().parent
FIXTURES=ROOT/'reference/original_replays'
REPORT=ROOT/'reference/compatibility_report.json'


def audit(selected=None,save=True):
    manifest=json.loads((FIXTURES/'manifest.json').read_text())
    sources={}
    for e in manifest:sources.setdefault(e['level_id'],[]).append(e)
    results=[]
    if selected is not None and not any(e['id']==selected for e in entries()):
        raise ValueError(f'Unknown installed level: {selected}')
    for spec in entries():
        if selected is not None and spec['id']!=selected:continue
        level=b.Level(spec['id'])
        row=dict(id=level.id,name=level.name,imported_objects=level.raw_count,
                 status='original_recording_needed',passed=False)
        if level.id in sources:
            checks=[]
            for source in sources[level.id]:
                path=FIXTURES/source['file']
                if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:
                    raise AssertionError(f'Original recording changed: {path.name}')
                replay=original_replays.load(path)
                result=original_replays.run(replay,level)
                result.pop('trace')
                result['recording']=source['file']
                result['recording_sha256']=source['sha256']
                checks.append(result)
            best=max(checks,key=lambda c:(c['passed'],c['progress']))
            row.update(best)
            row['checks']=checks
            row['status']='original_inputs_pass' if best['passed'] else 'physics_mismatch'
        results.append(row)
        print(f"{row['id']:4} {row['name']:25} {row['status']}"
              +(f" at {row['progress']:.2f}% ({row['mode']})" if 'progress' in row else ''),flush=True)
    if save:
        existing=json.loads(REPORT.read_text()) if REPORT.exists() and selected is not None else []
        replacements={r['id']:r for r in results}
        replacements.update((r['id'],r) for r in existing if r['id'] not in replacements)
        temporary=REPORT.with_suffix('.tmp')
        temporary.write_text(json.dumps(sorted(replacements.values(),key=lambda r:r['id']),indent=2)+'\n')
        temporary.replace(REPORT)
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level',type=int)
    parser.add_argument('--no-save',action='store_true')
    args=parser.parse_args()
    try:results=audit(args.level,not args.no_save)
    except ValueError as error:parser.error(str(error))
    raise SystemExit(0 if results and all(r['passed'] for r in results) else 1)
