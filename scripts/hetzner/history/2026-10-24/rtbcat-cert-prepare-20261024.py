from pathlib import Path
import shutil
import subprocess

backup = Path('/var/backups/rtbcat-remediation-20261024')
backup.mkdir(mode=0o700, parents=True, exist_ok=True)
target = Path('/etc/nginx/sites-available/rtbcat-mcp')
original = target.read_text()
needle = '    return 308 https://$host$request_uri;'
replacement = '''    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
        try_files $uri =404;
    }
    location / { return 308 https://$host$request_uri; }'''
assert original.count(needle) == 1
saved = backup / 'rtbcat-mcp.before'
assert not saved.exists(), 'Backup already exists; inspect before repeating'
shutil.copy2(target, saved)
shutil.copy2('/etc/nginx/sites-available/catscan-production', backup / 'catscan-production.before')
target.write_text(original.replace(needle, replacement))
try:
    subprocess.run(['nginx', '-t'], check=True)
except Exception:
    shutil.copy2(saved, target)
    raise
probe = Path('/var/www/html/.well-known/acme-challenge/rtbcat-renewal-probe-20261024')
probe.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
probe.write_text('rtbcat-renewal-probe-ok\n')
probe.chmod(0o644)
subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
print('MCP HTTP validation route installed; Nginx configuration valid and reloaded.')
