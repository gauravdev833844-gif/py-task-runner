"""Report secret binding presence and syntax only, never values or cookie hashes."""
import json
import os
from pathlib import Path


def main():
    value = os.environ.pop('YT_COOKIES', '')
    rows = []
    for line in value.splitlines():
        if line.startswith('#HttpOnly_'):
            line = line[len('#HttpOnly_'):]
        if not line or line.startswith('#'):
            continue
        fields = line.split('\t')
        domain = fields[0].lstrip('.').lower()
        if len(fields) >= 7 and (domain == 'youtube.com' or domain.endswith('.youtube.com')) and fields[-1]:
            rows.append(fields)
    result = {'repository': os.environ.get('GITHUB_REPOSITORY'), 'cookie_binding_present': bool(value),
              'cookie_format_valid': bool(rows), 'youtube_authentication_tested': False,
              'release_backup_default': True, 'overnight_workload_tested': False}
    value = ''; rows.clear()
    Path('setup-check.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    if not result['cookie_format_valid']:
        raise SystemExit('YT_COOKIES is missing or not a recognizable YouTube cookie file; set the private repository secret.')


if __name__ == '__main__':
    main()
