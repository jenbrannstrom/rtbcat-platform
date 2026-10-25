#!/usr/bin/env python3
"""Archive and remove expired bidstream rows in bounded transactions. Dry-run by default."""
import argparse
import datetime as dt
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid

GIB = 1024 ** 3

def emit(event, **fields):
    print(json.dumps(dict(event=event, **fields), sort_keys=True), flush=True)

def quote(value):
    return "'" + str(value).replace("'", "''") + "'"

class Psql:
    def __init__(self, database='rtbcat_serving', prefix=None):
        self.errors = tempfile.TemporaryFile()
        command = (prefix or ['psql']) + ['-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-d', database]
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.errors, text=True, bufsize=1,
                                     env=dict(os.environ, PGAPPNAME='rtbcat_bidstream_retention'))
        self.run("SET statement_timeout='45s'; SET lock_timeout='2s'; SET idle_in_transaction_session_timeout='120s'; SET max_parallel_workers_per_gather=0")

    def run(self, sql):
        marker = 'rtbcat_end_' + uuid.uuid4().hex
        self.proc.stdin.write(sql.rstrip(';') + ';\n\\echo ' + marker + '\n')
        self.proc.stdin.flush()
        lines = []
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError('psql stopped; transaction was not confirmed. Inspect PostgreSQL logs.')
            if line.rstrip('\n') == marker:
                return ''.join(lines).strip()
            lines.append(line)

    def data(self, sql):
        return json.loads(self.run(sql))

    def readonly(self, sql):
        self.run("BEGIN READ ONLY; SET LOCAL statement_timeout='180s'")
        try:
            return self.run(sql)
        finally:
            if self.proc.poll() is None:
                self.run('ROLLBACK')

    def close(self):
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=5)
        self.proc.stdout.close()
        self.errors.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

def policy(db):
    result = db.data("""SELECT json_build_object(
      'today',current_date,
      'values',(SELECT json_agg(raw_retention_days) FROM retention_config WHERE seat_id IS NULL),
      'longer_seats',(SELECT count(*) FROM retention_config WHERE seat_id IS NOT NULL
        AND raw_retention_days > (SELECT max(raw_retention_days) FROM retention_config WHERE seat_id IS NULL)))""")
    values = result['values'] or []
    if len(values) != 1 or type(values[0]) is not int or not 180 <= values[0] <= 365:
        raise RuntimeError('Exactly one global retention policy between 180 and 365 days is required')
    if result['longer_seats']:
        raise RuntimeError('A longer seat-specific retention policy requires separate handling')
    days = values[0]
    return days, dt.date.fromisoformat(result['today']) - dt.timedelta(days=days)

def schema(db):
    return db.data("""SELECT json_agg(json_build_object('name',attname,'type',format_type(atttypid,atttypmod),
      'not_null',attnotnull,'generated',attgenerated) ORDER BY attnum)
      FROM pg_attribute WHERE attrelid='public.rtb_bidstream'::regclass AND attnum>0 AND NOT attisdropped""")

def expired_check_sql(cutoff):
    # EXISTS can choose a full heap scan while its row estimate is stale after
    # deletion. A scalar, ordered LIMIT retains the date-index access path.
    return f"SELECT (SELECT metric_date FROM public.rtb_bidstream WHERE metric_date < {quote(cutoff)}::date ORDER BY metric_date LIMIT 1) IS NOT NULL"

def has_expired(db, cutoff):
    result=db.readonly(expired_check_sql(cutoff))
    if result not in ('t','f'):
        raise RuntimeError('Unexpected expiry verification result')
    return result=='t'

def durable_json(path, value):
    temp = path.with_name(path.name + '.tmp')
    with temp.open('x') as out:
        json.dump(value, out, indent=2)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def archive(rows, root, columns, cutoff):
    name = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex
    target = root / (name + '.jsonl.gz')
    header = dict(format='rtbcat-bidstream-jsonl-v1', table='public.rtb_bidstream', columns=columns,
                  cutoff=str(cutoff), row_count=len(rows))
    raw = (json.dumps(header) + '\n' + ''.join(json.dumps(item['row'], ensure_ascii=False) + '\n' for item in rows)).encode()
    with target.open('xb') as out:
        with gzip.GzipFile(fileobj=out, mode='wb', compresslevel=1, mtime=0) as compressed:
            compressed.write(raw)
        out.flush()
        os.fsync(out.fileno())
    if gzip.decompress(target.read_bytes()) != raw:
        raise RuntimeError('Archive verification failed; no rows may be removed')
    record = dict(header, archive=target.name, bytes=target.stat().st_size,
                  sha256=hashlib.sha256(target.read_bytes()).hexdigest(), state='archived-before-delete')
    manifest = root / (name + '.json')
    durable_json(manifest, record)
    return manifest, record

def batch(db, root, cutoff, days, columns, floor=None, size=50000):
    if not 1 <= size <= 100000:
        raise ValueError('Batch size must be 1..100000')
    db.run('BEGIN; LOCK TABLE public.retention_config IN SHARE MODE')
    try:
        current_days, current_cutoff = policy(db)
        if days != current_days or cutoff > current_cutoff:
            raise RuntimeError('Retention policy changed or cutoff would remove retained data')
        if schema(db) != columns:
            raise RuntimeError('Table definition changed; refusing archive/delete')
        lower = '' if floor is None else ' AND metric_date >= ' + quote(floor) + '::date'
        rows = db.data(f"""SELECT coalesce(json_agg(selected),'[]'::json) FROM (
          SELECT ctid::text AS tid,to_jsonb(b) AS row FROM public.rtb_bidstream b
          WHERE metric_date < {quote(cutoff)}::date {lower}
          ORDER BY metric_date LIMIT {int(size)} FOR UPDATE OF b SKIP LOCKED) selected""")
        if not rows:
            db.run('ROLLBACK')
            return None
        ids = [item['row']['id'] for item in rows]
        if len(ids) != len(set(ids)) or any(type(i) is not int for i in ids):
            raise RuntimeError('Unexpected or duplicate row IDs')
        for item in rows:
            if not re.fullmatch(r'\(\d+,\d+\)', item['tid']):
                raise RuntimeError('Unexpected physical row identifier')
            if dt.date.fromisoformat(item['row']['metric_date']) >= cutoff:
                raise RuntimeError('Selected a row inside the retention window')
        manifest, record = archive(rows, root, columns, cutoff)
        tids = ','.join(quote(item['tid']) for item in rows)
        removed = db.data(f"""WITH deleted AS (DELETE FROM public.rtb_bidstream
          WHERE ctid=ANY(ARRAY[{tids}]::tid[]) AND metric_date < {quote(cutoff)}::date RETURNING id)
          SELECT coalesce(json_agg(id),'[]'::json) FROM deleted""")
        if sorted(removed) != sorted(ids):
            raise RuntimeError('Deleted row IDs differ from the verified archive; rolling back')
        db.run('COMMIT')
        record['state'] = 'committed'
        record['committed_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        durable_json(manifest, record)
        return dict(rows=len(ids), bytes=record['bytes'], last_date=max(item['row']['metric_date'] for item in rows),
                    archive=record['archive'], sha256=record['sha256'])
    except Exception:
        if db.proc.poll() is None:
            try:
                db.run('ROLLBACK')
            except Exception:
                pass
        raise

def verify_backup():
    result = subprocess.run(['pgbackrest','--stanza=rtbcat','--log-level-file=off','--log-level-console=off',
                             '--output=json','info'], check=True, capture_output=True, text=True, timeout=120)
    stanza = next(s for s in json.loads(result.stdout) if s['name']=='rtbcat')
    stops = [b['timestamp']['stop'] for b in stanza.get('backup',[]) if not b.get('error')]
    if stanza['status']['code'] != 0 or not stops or time.time()-max(stops)>36*3600:
        raise RuntimeError('A healthy backup within 36 hours is required')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--batch-size', type=int, default=50000)
    parser.add_argument('--max-batches', type=int, default=10000)
    parser.add_argument('--once', action='store_true', help='Commit at most one batch for controlled validation')
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 100000 or not 1 <= args.max_batches <= 10000:
        parser.error('Invalid batch limits')
    os.umask(0o077)
    with Psql() as db:
        days, cutoff = policy(db)
        columns = schema(db)
        first = json.loads(db.readonly("SELECT coalesce((SELECT to_json(metric_date) FROM rtb_bidstream ORDER BY metric_date LIMIT 1),'null'::json)"))
        emit('plan',keep_days=days,cutoff=str(cutoff),first_date=first,apply=args.apply)
        if not args.apply:
            return
        volume=Path('/mnt/HC_Volume_106446141')
        if not volume.is_mount() or volume.stat().st_dev == Path('/var/lib/postgresql').stat().st_dev:
            raise RuntimeError('Separate mounted archive volume is required')
        root=volume/'retention-archives'/'bidstream'
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        with (root/'retention.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            verify_backup()
            floor=None
            total=0
            for number in range(args.max_batches):
                if shutil.disk_usage(volume).free < 40*GIB or shutil.disk_usage('/var/lib/postgresql').free < 80*GIB:
                    raise RuntimeError('Archive or database headroom below safety floor')
                ready=int(db.run("SELECT count(*) FROM pg_ls_dir('pg_wal/archive_status') f WHERE f LIKE '%.ready'"))
                if ready > 32:
                    raise RuntimeError('WAL archival backlog exceeds safety limit')
                result=batch(db,root,cutoff,days,columns,floor,args.batch_size)
                if result is None:
                    if not has_expired(db,cutoff):
                        emit('complete',removed_rows=total,cutoff=str(cutoff))
                        return
                    # Revisit earlier dates skipped due to concurrent row locks.
                    floor=None
                    time.sleep(1)
                    continue
                total+=result['rows']
                floor=result['last_date']
                emit('batch_committed',number=number+1,total_rows=total,**result)
                if args.once:
                    emit('single_batch_complete',removed_rows=total,cutoff=str(cutoff))
                    return
                time.sleep(0.1)
            raise RuntimeError('Batch limit reached; remaining work must run again')

if __name__=='__main__':
    main()
