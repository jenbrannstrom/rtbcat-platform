import datetime as dt
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import importlib.util
import os
import re

SPEC = importlib.util.spec_from_file_location(
    "bidstream_retention", Path(__file__).parents[1] / "scripts/hetzner/retain_bidstream.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

# Explicit opt-in; these tests replace tables only in a disposable Docker database.
CONTAINER = os.environ.get("RTBCAT_RETENTION_TEST_CONTAINER", "")
if CONTAINER and not re.fullmatch(r"rtbcat-retention-test-[a-z0-9-]+", CONTAINER):
    raise ValueError("Use a dedicated rtbcat-retention-test-* container")

PREFIX=['docker','exec','-i',CONTAINER,'psql','-U','postgres']

def connection():
    return m.Psql(database='rtbcat_retention_tests',prefix=PREFIX)

@unittest.skipUnless(CONTAINER, "Set RTBCAT_RETENTION_TEST_CONTAINER to an isolated test container")
class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.db=connection()
        self.addCleanup(self.db.close)
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db.run('''DROP TABLE IF EXISTS rtb_bidstream; DROP TABLE IF EXISTS retention_config;
          CREATE TABLE retention_config(seat_id text,raw_retention_days integer);
          INSERT INTO retention_config VALUES(NULL,180);
          CREATE TABLE rtb_bidstream(id integer PRIMARY KEY,metric_date date NOT NULL,hour integer,
            country text,buyer_account_id text,publisher_id text,publisher_name text,platform text,
            environment text,transaction_type text,inventory_matches bigint,bid_requests bigint,
            successful_responses bigint,reached_queries bigint,bids bigint,bids_in_auction bigint,
            auctions_won bigint,impressions bigint,clicks bigint,bidder_id text,report_type text,
            row_hash text UNIQUE,import_batch_id text,created_at timestamp,source_report text);
          INSERT INTO rtb_bidstream(id,metric_date,publisher_name,clicks,row_hash,created_at,source_report)
          VALUES(1,CURRENT_DATE-181,E'quotes '' and newline\\n日本',1152921504606846976,'oldhash',
                 TIMESTAMP '2026-01-02 03:04:05.123456',NULL),
                (2,CURRENT_DATE-180,'boundary',0,'keep1',NULL,'source'),
                (3,CURRENT_DATE,'current',NULL,'keep2',NULL,NULL),
                (4,CURRENT_DATE+1,'future',7,'keep3',NULL,NULL);''')
        self.days,self.cutoff=m.policy(self.db)
        self.columns=m.schema(self.db)

    def all_rows(self):
        return self.db.data('SELECT json_agg(to_jsonb(b) ORDER BY id) FROM rtb_bidstream b')

    def test_archive_round_trip_preserves_every_field_and_retained_boundary(self):
        before=self.all_rows()
        result=m.batch(self.db,self.root,self.cutoff,self.days,self.columns,size=2)
        self.assertEqual(result['rows'],1)
        self.assertEqual(self.all_rows(),before[1:])
        archive=self.root/result['archive']
        docs=[json.loads(line) for line in gzip.decompress(archive.read_bytes()).decode().splitlines()]
        self.assertEqual(docs[0]['columns'],self.columns)
        self.assertEqual(docs[1:],before[:1])
        manifest=json.loads(next(self.root.glob('*.json')).read_text())
        self.assertEqual(manifest['state'],'committed')
        # Actual PostgreSQL reconstruction verifies date/timestamp/bigint/NULL/text fidelity.
        for row in docs[1:]:
            self.db.run('INSERT INTO rtb_bidstream SELECT * FROM jsonb_populate_record(NULL::rtb_bidstream,'+m.quote(json.dumps(row))+'::jsonb)')
        self.assertEqual(self.all_rows(),before)

    def test_archive_failure_rolls_back_and_never_deletes(self):
        before=self.all_rows()
        with patch.object(m,'archive',side_effect=OSError('archive unavailable')):
            with self.assertRaises(OSError):
                m.batch(self.db,self.root,self.cutoff,self.days,self.columns)
        self.assertEqual(self.all_rows(),before)

    def test_corrupt_archive_prevents_deletion(self):
        before=self.all_rows()
        with patch.object(m.gzip,'decompress',return_value=b'corrupt'):
            with self.assertRaisesRegex(RuntimeError,'Archive verification'):
                m.batch(self.db,self.root,self.cutoff,self.days,self.columns)
        self.assertEqual(self.all_rows(),before)

    def test_policy_change_and_unsafe_cutoff_refused(self):
        before=self.all_rows()
        with self.assertRaisesRegex(RuntimeError,'cutoff'):
            m.batch(self.db,self.root,self.cutoff+dt.timedelta(days=1),self.days,self.columns)
        self.db.run('UPDATE retention_config SET raw_retention_days=181')
        with self.assertRaisesRegex(RuntimeError,'policy changed'):
            m.batch(self.db,self.root,self.cutoff,self.days,self.columns)
        self.db.run('UPDATE retention_config SET raw_retention_days=90')
        with self.assertRaisesRegex(RuntimeError,'180 and 365'):
            m.batch(self.db,self.root,self.cutoff,self.days,self.columns)
        self.assertEqual(self.all_rows(),before)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_longer_seat_policy_refused(self):
        self.db.run("INSERT INTO retention_config VALUES('longer-seat',365)")
        with self.assertRaisesRegex(RuntimeError,'longer seat-specific'):
            m.batch(self.db,self.root,self.cutoff,self.days,self.columns)
        self.assertEqual(len(self.all_rows()),4)

    def test_concurrent_locked_rows_are_preserved_then_processed(self):
        with connection() as other:
            other.run('BEGIN; SELECT id FROM rtb_bidstream WHERE id=1 FOR UPDATE')
            self.assertIsNone(m.batch(self.db,self.root,self.cutoff,self.days,self.columns))
            self.assertEqual(len(self.all_rows()),4)
            other.run('ROLLBACK')
        self.assertEqual(m.batch(self.db,self.root,self.cutoff,self.days,self.columns)['rows'],1)

    def test_schema_change_refused(self):
        self.db.run('ALTER TABLE rtb_bidstream ADD COLUMN future_metric bigint')
        with self.assertRaisesRegex(RuntimeError,'Table definition changed'):
            m.batch(self.db,self.root,self.cutoff,self.days,self.columns)
        self.assertEqual(len(self.all_rows()),4)

    def test_multiple_batches_and_empty_completion(self):
        self.db.run("INSERT INTO rtb_bidstream(id,metric_date) SELECT n,CURRENT_DATE-190 FROM generate_series(5,11) n")
        total=0
        for _ in range(4):
            result=m.batch(self.db,self.root,self.cutoff,self.days,self.columns,size=3)
            if result is None:
                break
            total+=result['rows']
        self.assertEqual(total,8)
        self.assertEqual([r['id'] for r in self.all_rows()],[2,3,4])
        self.assertIsNone(m.batch(self.db,self.root,self.cutoff,self.days,self.columns))

    def test_completion_check_uses_date_index_with_stale_statistics(self):
        self.db.run('''CREATE INDEX bidstream_test_date ON rtb_bidstream(metric_date);
          INSERT INTO rtb_bidstream(id,metric_date)
          SELECT n,CASE WHEN n<25100 THEN CURRENT_DATE-190 ELSE CURRENT_DATE END
          FROM generate_series(100,50099) n;
          ANALYZE rtb_bidstream;''')
        self.assertTrue(m.has_expired(self.db,self.cutoff))
        # Leave planner statistics stale, matching the actual post-delete case.
        self.db.run('DELETE FROM rtb_bidstream WHERE metric_date < CURRENT_DATE-180')
        plan=self.db.run('EXPLAIN '+m.expired_check_sql(self.cutoff))
        self.assertIn('bidstream_test_date',plan)
        self.assertNotIn('Seq Scan',plan)
        self.assertFalse(m.has_expired(self.db,self.cutoff))

if __name__=='__main__':
    unittest.main()
