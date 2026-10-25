#!/usr/bin/env python3
"""Check locally served public certificates, including name/trust and expiry."""
import datetime as dt
import json
import socket
import ssl

context=ssl.create_default_context()
failed=False
for domain in ['scan.rtb.cat','mcp.rtb.cat','scan-hetzner.rtb.cat']:
    try:
        with socket.create_connection(('127.0.0.1',443),timeout=10) as raw:
            with context.wrap_socket(raw,server_hostname=domain) as connection:
                expiry=ssl.cert_time_to_seconds(connection.getpeercert()['notAfter'])
        days=(expiry-dt.datetime.now(dt.timezone.utc).timestamp())/86400
        ok=days>=14
        failed|=not ok
        print(json.dumps(dict(domain=domain,days_remaining=round(days,2),ok=ok)),flush=True)
    except Exception as error:
        failed=True
        print(json.dumps(dict(domain=domain,ok=False,error_type=type(error).__name__)),flush=True)
raise SystemExit(1 if failed else 0)
