"""Prepare checked Windows downloads and publish only on the main release job."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1]
REPOSITORY='Samiul-Haque-vcode/Mellow_PDF-Reader'
TAG='v1.0.0'
ORIGINAL_TAG='755beea6f96e3a0541c392fa6b17be6ec6d0262a'


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def download_source(row,directory,opener=urllib.request.urlopen):
    """Download a pinned public archive without executing or extracting it."""
    if (not re.fullmatch(r'[a-z0-9][a-z0-9.-]*',row['name']) or
        not row['url'].startswith('https://download.qt.io/') or
        not re.fullmatch(r'[0-9a-f]{64}',row['sha256']) or
        type(row['bytes']) is not int or not 0<row['bytes']<1024**3):
        raise ValueError('Invalid pinned source archive.')
    target=Path(directory)/(row['name']+'.tar.xz');temporary=target.with_suffix('.part')
    if target.is_file() and target.stat().st_size==row['bytes'] and digest(target)==row['sha256']:return target
    try:
        size=0
        with opener(row['url'],timeout=60) as source,temporary.open('wb') as output:
            while block:=source.read(1024*1024):
                size+=len(block)
                if size>row['bytes']:raise ValueError('Source archive exceeds pinned size.')
                output.write(block)
        if size!=row['bytes'] or digest(temporary)!=row['sha256']:raise ValueError('Source archive hash/size mismatch.')
        temporary.replace(target)
    finally:temporary.unlink(missing_ok=True)
    return target


def zip_folder(folder,target):
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as output:
        for path in sorted(folder.rglob('*')):
            if path.is_symlink():raise ValueError('Release folders must not contain symbolic links.')
            if path.is_file():output.write(path,path.relative_to(folder.parent).as_posix())


def test_totals(path):
    root=ET.parse(path).getroot()
    suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
    totals={name:sum(int(s.get(name,0)) for s in suites) for name in ('tests','failures','errors','skipped')}
    if not totals['tests'] or totals['errors'] or totals['failures']:raise ValueError('Release requires passing Windows tests.')
    return totals


def prepare():
    commit=os.environ.get('GITHUB_SHA','')
    if not re.fullmatch(r'[0-9a-f]{40}',commit):raise ValueError('A release requires its exact source commit.')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,timeout=30).strip()
    if head!=commit:raise ValueError('The checkout does not match the release build commit.')
    dist=ROOT/'dist';out=dist/'release';out.mkdir(exist_ok=True)
    verification=dist/'build-verification'
    build=json.loads((verification/'BUILD.json').read_text(encoding='utf8'))
    security=json.loads((verification/'SECURITY.json').read_text(encoding='utf8'))
    attribution=json.loads((dist/'MellowPDFReader/licenses/DEPENDENCIES.json').read_text(encoding='utf8'))
    if build['commit']!=commit or security['defender']['status']!='NoThreatsReported' or not attribution['complete_attribution_review']:
        raise ValueError('Release verification or attribution is incomplete.')
    if security.get('changed_or_missing_files') or security.get('signature_error'):raise ValueError('Release verification has unresolved errors.')
    for row in build['files']:
        path=dist/row['path']
        if not path.resolve().is_relative_to(dist.resolve()) or not path.is_file() or digest(path)!=row['sha256']:
            raise ValueError('Checked build changed before publication.')
    totals=test_totals(ROOT/'test-results.xml')
    archives=json.loads((ROOT/'packaging/notices/SOURCE-ARCHIVES.json').read_text(encoding='utf8'))['archives']
    source_paths=[download_source(row,out) for row in archives]
    source=out/'MellowPDFReader-1.0.0-Source.zip'
    subprocess.run(['git','archive','--format=zip','--prefix=MellowPDFReader-1.0.0/','--output='+str(source),'HEAD'],cwd=ROOT,check=True,timeout=60)
    portable=dist/'MellowPDFReader-Portable'
    if not (portable/'portable.ini').is_file():raise ValueError('Portable marker is missing.')
    expected={r['path'].removeprefix('MellowPDFReader/'):r['sha256'] for r in build['files'] if r['path'].startswith('MellowPDFReader/')}
    actual={p.relative_to(portable).as_posix():digest(p) for p in portable.rglob('*') if p.is_file() and p.name!='portable.ini'}
    if actual!=expected:raise ValueError('Portable files do not match the checked app.')
    portable_zip=out/'MellowPDFReader-1.0.0-Portable-x64.zip';zip_folder(portable,portable_zip)
    installer=out/'MellowPDFReader-1.0.0-Setup-x64.exe';shutil.copy2(dist/'MellowPDFReader-Setup.exe',installer)
    evidence=out/'verification';evidence.mkdir(exist_ok=True)
    for name in ('BUILD.json','SHA256SUMS.txt'):shutil.copy2(verification/name,evidence/name)
    # Publish useful results rather than builder-specific absolute paths/logs.
    for row in security['signatures']:row['Path']=Path(row['Path']).name
    (evidence/'SECURITY.json').write_text(json.dumps(security,indent=2)+'\n',encoding='utf8')
    (evidence/'TESTS.json').write_text(json.dumps(dict(commit=commit,**totals),indent=2)+'\n',encoding='utf8')
    evidence_zip=out/'MellowPDFReader-1.0.0-Verification.zip';zip_folder(evidence,evidence_zip)
    paths=source_paths+[source,evidence_zip,installer,portable_zip]
    entries=[dict(name=p.name,bytes=p.stat().st_size,sha256=digest(p)) for p in paths]
    checksums=out/'SHA256SUMS.txt';checksums.write_text(''.join(f"{r['sha256']}  {r['name']}\n" for r in entries),encoding='utf8')
    entries.append(dict(name=checksums.name,bytes=checksums.stat().st_size,sha256=digest(checksums)))
    (out/'assets.json').write_text(json.dumps(dict(commit=commit,files=entries),indent=2)+'\n',encoding='utf8')
    notes=(ROOT/'docs/releases/1.0.0.md').read_text(encoding='utf8').replace('{{BUILD_COMMIT}}',commit).replace('{{PASSED_TESTS}}',str(totals['tests']-totals['skipped']))
    (out/'release-notes.md').write_text(notes,encoding='utf8')
    print('Prepared',len(entries),'verified release assets; tests:',totals)


def github_cli(*args):
    # GitHub CLI emits UTF-8 even when Windows uses a legacy system code page.
    command=['gh',*args]
    if args[0]!='api':command+=['--repo',REPOSITORY]
    return subprocess.run(command,cwd=ROOT,check=True,capture_output=True,
                          text=True,encoding='utf8',timeout=600).stdout


def publish():
    if os.environ.get('GITHUB_REF')!='refs/heads/main' or os.environ.get('GITHUB_REPOSITORY')!=REPOSITORY:
        raise ValueError('Publication is restricted to the intended repository main branch.')
    out=ROOT/'dist/release';data=json.loads((out/'assets.json').read_text(encoding='utf8'))
    if data['commit']!=os.environ.get('GITHUB_SHA'):raise ValueError('Release commit changed.')
    assets=[]
    for row in data['files']:
        if Path(row['name']).name!=row['name']:raise ValueError('Invalid release asset path.')
        path=out/row['name']
        if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:raise ValueError('Release asset changed.')
        assets.append(path)
    release=json.loads(github_cli('api','repos/'+REPOSITORY+'/releases/tags/'+TAG))
    tag=json.loads(github_cli('api','repos/'+REPOSITORY+'/git/ref/tags/'+TAG))
    if release['tag_name']!=TAG or tag['object']['sha']!=ORIGINAL_TAG:raise ValueError('Existing public source tag changed; publication stopped.')
    # Make corresponding source accessible before publishing any executable.
    sources=[p for p in assets if p.name.endswith('.tar.xz') or p.name.endswith('-Source.zip')]
    github_cli('release','upload',TAG,*map(str,sources),'--clobber')
    github_cli('release','upload',TAG,*[str(p) for p in assets if p not in sources],'--clobber')
    github_cli('release','edit',TAG,'--title','Mellow PDF Reader 1.0.0','--notes-file',str(out/'release-notes.md'))
    published=json.loads(github_cli('api','repos/'+REPOSITORY+'/releases/tags/'+TAG))
    available={r['name']:r for r in published['assets']}
    for row in data['files']:
        remote=available.get(row['name'],{})
        if remote.get('size')!=row['bytes'] or remote.get('state')!='uploaded':raise ValueError('Published release asset is incomplete.')
        if remote.get('digest') and remote['digest']!='sha256:'+row['sha256']:raise ValueError('Published release asset hash mismatch.')
    print('Published and verified',len(assets),'assets:',published['html_url'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish',action='store_true')
    args=parser.parse_args()
    publish() if args.publish else prepare()
