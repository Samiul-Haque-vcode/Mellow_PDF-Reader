"""Read-only verification of the existing Windows 1.0.0 release downloads."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request
import zipfile
from release_assets import github_cli,REPOSITORY,TAG,ORIGINAL_TAG,ROOT

def check_evidence(build,security,tests,body,expected_build=None):
    commit=build.get('commit')
    if not isinstance(commit,str) or not re.fullmatch('[0-9a-f]{40}',commit):
        raise ValueError('Build evidence has an invalid source commit.')
    if expected_build is not None and commit!=expected_build:
        raise ValueError('Verification evidence identifies a different build.')
    if tests.get('commit')!=commit or build.get('python')!='3.14.10' or commit not in body:
        raise ValueError('Verification evidence identifies a different build.')
    if (any(type(tests.get(k)) is not int or tests[k]<0 for k in ('tests','errors','failures','skipped')) or
        not tests['tests'] or tests['errors'] or tests['failures'] or tests['skipped']):
        raise ValueError('Windows test evidence is incomplete.')
    if (security['defender']['status']!='NoThreatsReported' or security['changed_or_missing_files'] or
        security.get('signature_error') or len(security['signatures'])!=2):
        raise ValueError('Security evidence is incomplete.')
    return commit


def verify(expected_build=None):
    release=json.loads(github_cli('api','repos/'+REPOSITORY+'/releases/tags/'+TAG))
    tag=json.loads(github_cli('api','repos/'+REPOSITORY+'/git/ref/tags/'+TAG))
    if release['tag_name']!=TAG or tag['object']['sha']!=ORIGINAL_TAG:
        raise ValueError('Published release identity changed.')
    assets={row['name']:row for row in release['assets']}
    def fetch(name,limit):
        row=assets[name]
        prefix='https://github.com/'+REPOSITORY+'/releases/download/'+TAG+'/'
        if not row['browser_download_url'].startswith(prefix) or not 0<row['size']<=limit:
            raise ValueError('Unexpected release download.')
        with urllib.request.urlopen(row['browser_download_url'],timeout=40) as response:body=response.read(limit+1)
        if len(body)!=row['size'] or row.get('digest')!='sha256:'+hashlib.sha256(body).hexdigest():
            raise ValueError('Downloaded release evidence hash/size mismatch.')
        return body
    checksums={}
    for line in fetch('SHA256SUMS.txt',16384).decode('utf8').splitlines():
        sha,name=line.split('  ',1)
        if not re.fullmatch('[0-9a-f]{64}',sha) or name in checksums or Path(name).name!=name:
            raise ValueError('Invalid release checksums.')
        checksums[name]=sha
    required={'MellowPDFReader-1.0.0-'+suffix for suffix in ('Setup-x64.exe','Portable-x64.zip','Source.zip','Verification.zip')}
    archives=json.loads((ROOT/'packaging/notices/SOURCE-ARCHIVES.json').read_text(encoding='utf8'))['archives']
    required.update(row['name']+'.tar.xz' for row in archives)
    if set(checksums)!=required:raise ValueError('Release downloads are incomplete.')
    for name,sha in checksums.items():
        row=assets.get(name,{})
        if row.get('digest')!='sha256:'+sha or row.get('state')!='uploaded' or row.get('size',0)<=0:
            raise ValueError('Published asset mismatch: '+name)
    for row in archives:
        asset=assets[row['name']+'.tar.xz']
        if asset['size']!=row['bytes'] or asset['digest']!='sha256:'+row['sha256']:
            raise ValueError('Corresponding source archive changed.')
    with zipfile.ZipFile(io.BytesIO(fetch('MellowPDFReader-1.0.0-Verification.zip',1024*1024))) as bundle:
        evidence={}
        for name in ('BUILD.json','SECURITY.json','TESTS.json'):
            path='verification/'+name
            if bundle.getinfo(path).file_size>5*1024*1024:raise ValueError('Oversized verification evidence.')
            evidence[name]=json.loads(bundle.read(path))
    build,security,tests=(evidence[n] for n in ('BUILD.json','SECURITY.json','TESTS.json'))
    commit=check_evidence(build,security,tests,release['body'],expected_build)
    installer=next(row for row in build['files'] if row['path']=='MellowPDFReader-Setup.exe')
    if installer['sha256']!=checksums['MellowPDFReader-1.0.0-Setup-x64.exe']:
        raise ValueError('Installer does not match the scanned build.')
    print('Verified all 10 published assets and corresponding sources.')
    print('Build:',commit,'Python:',build['python'],'Windows tests:',tests['tests'])
    print('Defender:',security['defender']['status'],'Signatures:',[r['Status'] for r in security['signatures']])
    print('Read-only verification completed; no assets uploaded or modified.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit',help='Require this exact source commit in the published build evidence')
    args=parser.parse_args()
    verify(args.commit)
