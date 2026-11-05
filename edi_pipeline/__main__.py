"""CLI: local file ingestion with content-based replay protection."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import sqlite3
import time
from .core import parse, ValidationError

def write_json(path, value):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    temp.replace(path)

def run(source, output):
    source, output = Path(source), Path(output)
    if not source.is_dir():
        raise ValueError('Input directory does not exist')
    if source.resolve() == output.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError('Output must be outside the input directory')
    for folder in ['accepted','quarantine']:
        (output/folder).mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(output/'monitoring.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS processed (digest TEXT PRIMARY KEY, status TEXT, kind TEXT, source TEXT, detail TEXT, elapsed_ms REAL, timestamp TEXT)')
    counts = Counter(accepted=0, rejected=0, duplicate=0)
    try:
        for path in sorted(source.rglob('*.edi')):
            start = time.perf_counter()
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if db.execute('SELECT 1 FROM processed WHERE digest=?',(digest,)).fetchone():
                counts['duplicate'] += 1
                continue
            stamp = datetime.now(timezone.utc).isoformat()
            kind, detail = '', ''
            try:
                record = parse(raw.decode('ascii'))
                kind = record['transaction_type']
                record.update(source_file=path.name, sha256=digest, processed_at=stamp)
                write_json(output/'accepted'/f'{digest}.json',record)
                status = 'accepted'
            except (ValidationError, UnicodeDecodeError) as exc:
                detail = str(exc)
                status = 'rejected'
                # Original bytes preserved; no partial transformed output is emitted.
                (output/'quarantine'/f'{digest}.edi').write_bytes(raw)
                write_json(output/'quarantine'/f'{digest}.error.json',
                           {'source_file':path.name, 'sha256':digest, 'error':detail, 'timestamp':stamp})
            elapsed = round((time.perf_counter()-start)*1000,3)
            db.execute('INSERT INTO processed VALUES (?,?,?,?,?,?,?)',
                       (digest,status,kind,path.name,detail,elapsed,stamp))
            db.commit()
            counts[status] += 1
            with (output/'events.jsonl').open('a', encoding='utf-8') as log:
                log.write(json.dumps(dict(source=path.name,status=status,error=detail,elapsed_ms=elapsed,timestamp=stamp))+'\n')
        rows = db.execute('SELECT status,kind,source,detail,elapsed_ms,timestamp FROM processed ORDER BY timestamp DESC').fetchall()
        total = Counter(r[0] for r in rows)
        summary = {'last_run':dict(counts), 'cumulative_unique_files':dict(total), 'updated_at':datetime.now(timezone.utc).isoformat()}
        write_json(output/'summary.json',summary)
        cells = ''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in r)+'</tr>' for r in rows)
        (output/'dashboard.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>X12 Pipeline Monitor</title><style>body{font:16px system-ui;background:#101827;color:#e5eaf2;margin:4vw}h1{color:#64d8cc}table{border-collapse:collapse;width:100%;background:#182438}td,th{padding:12px;text-align:left;border-bottom:1px solid #35445a}pre{padding:20px;background:#182438;white-space:pre-wrap}a{color:#64d8cc}</style><h1>X12 Integration Monitor</h1><p>Synthetic data · local batch processing · refresh after each run</p><pre>'''+html.escape(json.dumps(summary,indent=2))+'''</pre><h2>Unique file history</h2><table><tr><th>Status</th><th>X12</th><th>Source</th><th>Error</th><th>Latency ms</th><th>UTC timestamp</th></tr>'''+cells+'</table></html>',encoding='utf-8')
        print(json.dumps(summary,indent=2))
        return counts
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',default='samples')
    parser.add_argument('--output',default='output')
    parser.add_argument('--fail-on-rejection',action='store_true')
    args = parser.parse_args()
    counts = run(args.input,args.output)
    if args.fail_on_rejection and counts['rejected']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
