from pathlib import Path
import hashlib
import json

root=Path('/mnt/HC_Volume_106446141/retention-archives/bidstream')
records=[]
for manifest in sorted(root.glob('*.json')):
    record=json.loads(manifest.read_text())
    assert record['state']=='committed', manifest.name
    assert record['cutoff']=='2026-04-27', manifest.name
    assert record['table']=='public.rtb_bidstream', manifest.name
    assert len(record['columns'])==25, manifest.name
    assert Path(record['archive']).name==record['archive']
    archive=root/record['archive']
    assert archive.stat().st_size==record['bytes'], archive.name
    digest=hashlib.sha256()
    with archive.open('rb') as source:
        for chunk in iter(lambda:source.read(8*1024*1024),b''):
            digest.update(chunk)
    assert digest.hexdigest()==record['sha256'], archive.name
    records.append(record)
assert len(records)==len(list(root.glob('*.jsonl.gz')))
assert not list(root.glob('*.tmp'))
rows=sum(record['row_count'] for record in records)
assert rows==61985593, rows
print(json.dumps({'committed_archives':len(records),'archived_rows':rows,
                  'compressed_bytes':sum(record['bytes'] for record in records),
                  'all_checksums_match':True,'all_columns':25,'cutoff':'2026-04-27'}))
