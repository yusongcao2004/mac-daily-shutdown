#!/usr/bin/env python3
"""Read personal-file metadata; keep dated snapshots for the daily report."""
import collections
import datetime as dt
import json
import os
from pathlib import Path
from settings import APP_HOME, CONFIG

BASE = Path(__file__).resolve().parent
USER = Path.home()
STATE = APP_HOME / 'daily-report-state'
SKIP = {'.git', 'node_modules', '.next', '.venv', 'venv', '__pycache__',
        '.cache', '.turbo', '.pytest_cache', 'dist', 'build', 'coverage',
        'Caches', 'Cache', '.DS_Store', '.Trash'}
PACKAGES = ('.app', '.photoslibrary', '.photolibrary')

def main():
    os.umask(0o077)
    now = dt.datetime.now(dt.timezone.utc)
    end = now.timestamp()
    start = end - 86400
    STATE.mkdir(parents=True, exist_ok=True)
    previous_files = sorted(STATE.glob('snapshot-*.json'))
    previous = json.loads(previous_files[-1].read_text()) if previous_files else None
    errors, skipped, files = [], [], {}
    roots = [str(Path(p).expanduser().resolve()) for p in
        CONFIG.get('scan_roots', ['~/Desktop', '~/Documents', '~/Downloads'])]
    stack = list(roots)
    while stack:
        path = Path(stack.pop())
        if path in {BASE.parent, APP_HOME} or path.name in SKIP or path.name.endswith(PACKAGES):
            skipped.append(str(path)); continue
        try:
            if path.is_symlink():
                skipped.append(str(path)); continue
            if path.is_dir():
                with os.scandir(path) as entries:
                    stack.extend(e.path for e in entries)
                continue
            s = path.stat()
            files[str(path)] = {'size': s.st_size, 'mtime_ns': s.st_mtime_ns,
                'birthtime': getattr(s, 'st_birthtime', 0), 'ctime_ns': s.st_ctime_ns,
                'inode': s.st_ino, 'device': s.st_dev}
        except OSError as exc:
            errors.append({'path': str(path), 'error': str(exc)})
    recent = []
    for path, item in files.items():
        if any(start <= t <= end for t in [item['mtime_ns']/1e9, item['birthtime'], item['ctime_ns']/1e9]):
            recent.append({'path': path, **item,
                'time_evidence': [kind for kind,t in [('modified',item['mtime_ns']/1e9),
                    ('created_on_volume',item['birthtime']),('metadata_changed',item['ctime_ns']/1e9)] if start<=t<=end]})
    added, changed, missing = [], [], []
    if previous:
        old = previous['files']
        added = sorted(set(files)-set(old))
        changed = sorted(p for p in files.keys() & old.keys() if files[p] != old[p])
        # Missing paths are observations, not confirmed deletions (permissions/mounts may change).
        missing = sorted(set(old)-set(files))
    summary = {'window_start': dt.datetime.fromtimestamp(start,dt.timezone.utc).isoformat(),
        'window_end': now.isoformat(), 'roots': sorted(roots), 'errors': errors,
        'excluded': sorted(skipped), 'file_count': len(files), 'recent_count': len(recent),
        'baseline_time': previous['captured_at'] if previous else None,
        'newly_observed_since_baseline': added, 'metadata_changed_since_baseline': changed,
        'missing_since_baseline_not_confirmed_deleted': missing,
        'recent': sorted(recent,key=lambda x:x['mtime_ns'],reverse=True)}
    stamp = now.strftime('%Y%m%dT%H%M%SZ')
    (STATE/f'snapshot-{stamp}.json').write_text(json.dumps({'captured_at':now.isoformat(),'files':files},ensure_ascii=False))
    target = STATE/f'scan-{stamp}.json'
    target.write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps({'scan':str(target),'files':len(files),'recent':len(recent),
        'errors':errors,'recent_by_root':dict(collections.Counter(str(Path(x['path']).parent) for x in recent))},ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
