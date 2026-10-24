"""Sign named release files with an existing Windows certificate-store identity.

No certificate/private key is created, exported or uploaded. signtool and a
trusted code-signing certificate with an accessible private key are required.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlparse


def sign(paths, thumbprint, timestamp='https://timestamp.digicert.com', executable=None):
    thumbprint=thumbprint.replace(' ', '')
    if not re.fullmatch(r'[a-fA-F0-9]{40}', thumbprint):
        raise ValueError('Use the 40-digit SHA-1 certificate thumbprint from the Windows certificate store.')
    endpoint=urlparse(timestamp)
    if endpoint.scheme != 'https' or not endpoint.hostname or endpoint.username or endpoint.password:
        raise ValueError('The RFC 3161 timestamp server must be an HTTPS URL without credentials.')
    files=[Path(path).resolve() for path in paths]
    if not files or any(not path.is_file() for path in files):
        raise ValueError('Every file to sign must already exist.')
    tool=executable or shutil.which('signtool.exe')
    if not tool:
        sdk=Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)'))/'Windows Kits/10/bin'
        tool=next((str(p) for p in sorted(sdk.glob('*/x64/signtool.exe'), reverse=True)), None)
    if not tool:
        raise OSError('Install Windows SDK Signing Tools or put signtool.exe on PATH.')
    for path in files:
        subprocess.run([str(tool), 'sign', '/sha1', thumbprint, '/s', 'My',
                        '/fd', 'SHA256', '/tr', timestamp, '/td', 'SHA256', str(path)],
                       check=True, timeout=180)
        subprocess.run([str(tool), 'verify', '/pa', '/all', '/v', str(path)],
                       check=True, timeout=60)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--thumbprint', required=True)
    parser.add_argument('--timestamp', default='https://timestamp.digicert.com')
    parser.add_argument('files', nargs='+')
    args=parser.parse_args()
    if os.name != 'nt':
        parser.error('Signing requires Windows and your certificate-store identity.')
    sign(args.files, args.thumbprint, args.timestamp)


if __name__ == '__main__':
    main()
