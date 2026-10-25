from pathlib import Path
import shutil
import subprocess

backup = Path('/var/backups/rtbcat-remediation-20261024')
backup.mkdir(mode=0o700, parents=True, exist_ok=True)
pam = Path('/etc/pam.d/login')
text = pam.read_text()
needle = 'session    optional   pam_lastlog.so'
assert text.count(needle) == 1
assert not Path('/usr/lib/x86_64-linux-gnu/security/pam_lastlog.so').exists()
shutil.copy2(pam, backup / 'pam-login.before')
pam.write_text(text.replace(needle, '# Obsolete optional pam_lastlog.so removed: module absent on Ubuntu 24.04.'))

rule = Path('/etc/udev/rules.d/90-cloud-init-hook-hotplug.rules')
text = rule.read_text()
needle = 'ACTION!="add", GOTO="cloudinit_end"\n'
assert text.count(needle) == 1
assert 'ATTR{address}=="86:*"' in text
shutil.copy2(rule, backup / '90-cloud-init-hook-hotplug.rules.before')
rule.write_text(text.replace(needle, needle + '# Docker/veth devices are not cloud NICs, even if their MAC starts with 86.\nDEVPATH=="/devices/virtual/net/*", GOTO="cloudinit_end"\n'))
subprocess.run(['udevadm', 'verify', str(rule)], check=True)
subprocess.run(['udevadm', 'control', '--reload-rules'], check=True)
subprocess.run(['systemctl', 'reset-failed', 'cloud-init-hotplugd.service'], check=True)

motd = Path('/etc/update-motd.d/50-motd-news')
assert motd.stat().st_mode & 0o777 == 0o644
shutil.copy2(motd, backup / '50-motd-news.before')
motd.chmod(0o755)
subprocess.run(['systemctl', 'start', 'motd-news.service'], check=True)
print('Optional obsolete PAM entry removed; virtual-NIC cloud-init guard verified; MOTD execution repaired.')
