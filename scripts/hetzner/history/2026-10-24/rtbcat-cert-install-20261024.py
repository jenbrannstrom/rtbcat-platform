from pathlib import Path
import shutil
import subprocess

backup = Path('/var/backups/rtbcat-remediation-20261024')
new = '/etc/letsencrypt/live/rtbcat-production/'
assert Path(new, 'fullchain.pem').is_file()
for name, old in [
    ('catscan-production', '/etc/rtbcat/tls/scan.rtb.cat/'),
    ('rtbcat-mcp', '/etc/letsencrypt/live/mcp.rtb.cat/'),
]:
    target = Path('/etc/nginx/sites-available') / name
    content = target.read_text()
    assert content.count(old) == 2, name
    shutil.copy2(target, backup / (name + '.pre-certificate'))
    target.write_text(content.replace(old, new))
try:
    subprocess.run(['nginx', '-t'], check=True)
except Exception:
    for name in ['catscan-production', 'rtbcat-mcp']:
        shutil.copy2(backup / (name + '.pre-certificate'), Path('/etc/nginx/sites-available') / name)
    raise
hook = Path('/etc/letsencrypt/renewal-hooks/deploy/50-rtbcat-nginx-reload')
assert not hook.exists()
hook.write_text('#!/bin/sh\nset -eu\n/usr/sbin/nginx -t\n/bin/systemctl reload nginx\n')
hook.chmod(0o755)
subprocess.run([str(hook)], check=True)
subprocess.run(['systemctl', 'enable', '--now', 'certbot.timer'], check=True)
Path('/var/www/html/.well-known/acme-challenge/rtbcat-renewal-probe-20261024').unlink()
print('Both production names use the managed certificate; renewal deploy hook installed.')
