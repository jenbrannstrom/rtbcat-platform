#!/usr/bin/env python3
"""Archive expired rtb_daily months before removing them; read-only by default."""

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

DATABASE = "rtbcat_serving"
PARENT = "public.rtb_daily"
NAME = re.compile(r"rtb_daily_(\d{4})(\d{2})\Z")
BOUNDS = re.compile(r"FOR VALUES FROM \('([0-9-]+)'\) TO \('([0-9-]+)'\)\Z")


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}, sort_keys=True), flush=True)


def sql(statement, *, write=False):
    prefix = "BEGIN;" if write else "BEGIN READ ONLY;"
    command = prefix + " SET LOCAL lock_timeout='2s'; SET LOCAL statement_timeout='30s'; " + statement + "; COMMIT;"
    result = subprocess.run(
        ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", DATABASE, "-c", command],
        text=True, capture_output=True, check=True, cwd="/",
    )
    return result.stdout.strip()


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def next_month(value):
    return dt.date(value.year + value.month // 12, value.month % 12 + 1, 1)


def expired(partition, cutoff):
    name = NAME.fullmatch(partition["name"])
    bounds = BOUNDS.fullmatch(partition["bounds"])
    if not name or not bounds:
        raise ValueError("Unexpected partition name/bounds; refusing automatic removal")
    start, end = map(dt.date.fromisoformat, bounds.groups())
    expected = dt.date(int(name[1]), int(name[2]), 1)
    if start != expected or end != next_month(start):
        raise ValueError("Partition name does not match actual monthly bounds")
    return end <= cutoff


def retention_days(config, minimum):
    values = {row["raw_retention_days"] for row in config}
    if len(values) != 1:
        raise ValueError("Global retention settings are missing or disagree")
    value = values.pop()
    if not isinstance(value, int) or not minimum <= value <= 365:
        raise ValueError("Retention falls outside the approved range")
    return value


def inventory(minimum):
    data = json.loads(sql("""
        SELECT json_build_object(
          'today',current_date,
          'config',(SELECT json_agg(json_build_object('raw_retention_days',raw_retention_days)) FROM retention_config WHERE seat_id IS NULL),
          'partitions',(SELECT json_agg(json_build_object('name',c.relname,'oid',c.oid,'bounds',pg_get_expr(c.relpartbound,c.oid),'bytes',pg_total_relation_size(c.oid),'heap_bytes',pg_table_size(c.oid))) FROM pg_inherits i JOIN pg_class c ON c.oid=i.inhrelid WHERE i.inhparent='public.rtb_daily'::regclass))
    """))
    days = retention_days(data["config"] or [], minimum)
    today = dt.date.fromisoformat(data["today"])
    cutoff = today - dt.timedelta(days=days)
    candidates = [p for p in data["partitions"] if expired(p, cutoff)]
    return today, days, cutoff, sorted(candidates, key=lambda p: p["name"])


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_backup():
    result = subprocess.run(
        ["pgbackrest", "--log-level-file=off", "--log-level-console=off", "--output=json", "info"],
        check=True, capture_output=True, text=True, timeout=120,
    )
    stanzas = json.loads(result.stdout)
    stanza = next(s for s in stanzas if s["name"] == "rtbcat")
    stops = [b["timestamp"]["stop"] for b in stanza.get("backup", []) if not b.get("error")]
    now = dt.datetime.now(dt.timezone.utc).timestamp()
    if stanza["status"]["code"] != 0 or not stops or now - max(stops) > 36 * 3600:
        raise RuntimeError("No healthy backup completed within 36 hours")


def archive_partition(partition, root):
    target = root / (partition["name"] + ".dump")
    manifest = root / (partition["name"] + ".json")
    if target.exists() or manifest.exists():
        record = json.loads(manifest.read_text())
        if record["partition"] != partition or record["sha256"] != sha256(target):
            raise RuntimeError("Existing archive is not a verified match for this partition")
        return target
    if shutil.disk_usage(root).free < max(40 * 1024**3, partition["heap_bytes"] * 2):
        raise RuntimeError("Insufficient archive-volume headroom")
    partial = target.with_suffix(".dump.partial")
    if partial.exists():
        raise RuntimeError("Incomplete archive exists; manual inspection required")
    subprocess.run(
        ["pg_dump", "-d", DATABASE, "-Fc", "-Z", "1", "--strict-names", "--lock-wait-timeout=5s",
         "--table=" + PARENT, "--table=public." + partition["name"], "--file=" + str(partial)],
        check=True, stdout=subprocess.DEVNULL,
    )
    listing = subprocess.run(["pg_restore", "--list", str(partial)], check=True, text=True, capture_output=True)
    if not any("TABLE DATA public " + partition["name"] + " " in line for line in listing.stdout.splitlines()):
        raise RuntimeError("Archive does not contain the intended partition data")
    subprocess.run(
        ["pg_restore", "--exit-on-error", "--data-only", "--file=/dev/null", str(partial)],
        check=True, stdout=subprocess.DEVNULL,
    )
    digest = sha256(partial)
    partial.rename(target)
    record = {"partition": partition, "sha256": digest, "bytes": target.stat().st_size,
              "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "validation": "Complete pg_restore data decode; no restore rehearsal"}
    with manifest.open("x") as output:
        json.dump(record, output, indent=2)
        output.flush()
        os.fsync(output.fileno())
    emit("archive_verified", partition=partition["name"], archive=str(target), bytes=record["bytes"], sha256=digest)
    return target


def remove_partition(partition, cutoff, days):
    # Names and actual bounds were validated by expired(); do not use CASCADE.
    if not expired(partition, cutoff):
        raise ValueError("Partition still overlaps the retention window")
    statement = f"""
      LOCK TABLE public.rtb_daily IN ACCESS EXCLUSIVE MODE;
      DO $guard$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_inherits i JOIN pg_class c ON c.oid=i.inhrelid
          WHERE i.inhparent='public.rtb_daily'::regclass AND c.oid={int(partition['oid'])}
          AND c.relname={quote(partition['name'])}
          AND pg_get_expr(c.relpartbound,c.oid)={quote(partition['bounds'])}) THEN
          RAISE EXCEPTION 'Partition changed since archive';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM retention_config WHERE seat_id IS NULL)
          OR EXISTS (SELECT 1 FROM retention_config WHERE seat_id IS NULL AND raw_retention_days IS DISTINCT FROM {days}) THEN
          RAISE EXCEPTION 'Retention configuration changed';
        END IF;
      END $guard$;
      DROP TABLE public.{partition['name']}
    """
    sql(statement, write=True)
    emit("partition_removed", partition=partition["name"], bytes=partition["bytes"], cutoff=cutoff.isoformat())


def ensure_ahead(today):
    month = today.replace(day=1)
    for _ in range(4):
        name = "rtb_daily_" + month.strftime("%Y%m")
        following = next_month(month)
        exists = sql(f"SELECT to_regclass({quote('public.' + name)}) IS NOT NULL")
        if exists == "t":
            month = following
            continue
        # Each month commits separately; missing partitions inherit the current indexes.
        sql(f"""
          CREATE TABLE IF NOT EXISTS public.{name} PARTITION OF public.rtb_daily
          FOR VALUES FROM ({quote(month)}) TO ({quote(following)});
          ALTER TABLE public.{name} OWNER TO rtbcat_serving
        """, write=True)
        month = following


def process_candidates(candidates, root, cutoff, days):
    for partition in candidates:
        archive_partition(partition, root)
        remove_partition(partition, cutoff, days)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--minimum-days", type=int, default=180)
    parser.add_argument("--archive-volume", type=Path, default=Path("/mnt/HC_Volume_106446141"))
    args = parser.parse_args()
    today, days, cutoff, candidates = inventory(args.minimum_days)
    emit("plan", keep_days=days, cutoff=cutoff.isoformat(), partitions=candidates,
         total_bytes=sum(p["bytes"] for p in candidates), apply=args.apply)
    if not args.apply:
        return
    if not args.archive_volume.is_mount() or args.archive_volume.stat().st_dev == Path("/var/lib/postgresql").stat().st_dev:
        raise RuntimeError("Archive must be on the expected separate mounted volume")
    os.umask(0o077)
    root = args.archive_volume / "retention-archives" / "partitions"
    root.mkdir(parents=True, exist_ok=True)
    with (root / "retention.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        verify_backup()
        process_candidates(candidates, root, cutoff, days)
        ensure_ahead(today)
    emit("complete", removed=len(candidates))


if __name__ == "__main__":
    main()
