"""Publish build hashes, Authenticode status and an explicit Defender result.

This checks files; it does not sign them, alter Windows protection settings or
interpret an unavailable antivirus scanner as a successful scan.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

IS_WINDOWS=os.name=='nt'


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()


def build_manifest(distribution,installer,output):
    distribution,installer,output=Path(distribution).resolve(),Path(installer).resolve(),Path(output).resolve()
    if not distribution.is_dir() or not installer.is_file(): raise ValueError('The complete app folder and installer must exist.')
    if output==distribution or distribution in output.parents: raise ValueError('Keep verification reports outside the app folder.')
    root=distribution.parent
    files=sorted([p for p in distribution.rglob('*') if p.is_file()]+[installer])
    entries=[dict(path=p.relative_to(root).as_posix(),sha256=sha256(p),bytes=p.stat().st_size) for p in files]
    output.mkdir(parents=True,exist_ok=True)
    (output/'SHA256SUMS.txt').write_text(''.join(f"{r['sha256']}  {r['path']}\n" for r in entries),encoding='utf8')
    packages=sorted((dict(name=d.metadata['Name'],version=d.version) for d in metadata.distributions()),key=lambda d:d['name'].casefold())
    data=dict(created_utc=datetime.now(timezone.utc).isoformat(),commit=os.environ.get('GITHUB_SHA'),
              python=platform.python_version(),platform=platform.platform(),files=entries,build_packages=packages,
              note='Hashes identify exact build files. They do not prove that software is safe or signed.')
    (output/'BUILD.json').write_text(json.dumps(data,indent=2),encoding='utf8')
    return data


def ps_quote(value):
    return "'"+str(value).replace("'","''")+"'"


def powershell_json(script):
    executable=shutil.which('pwsh.exe') or 'powershell.exe'
    result=subprocess.run([executable,'-NoProfile','-NonInteractive','-Command',script],
                          capture_output=True,text=True,timeout=30)
    if result.returncode: raise OSError(result.stderr.strip() or result.stdout.strip() or f'PowerShell exited {result.returncode}')
    return json.loads(result.stdout.strip().lstrip('\ufeff'))


def authenticode(paths):
    # Process each literal file separately and serialize plain objects. This
    # works on both Windows PowerShell and PowerShell 7 without adapting enums
    # or invoking calculated-property parsing in Select-Object.
    literal=','.join(ps_quote(p) for p in paths)
    script="$ErrorActionPreference='Stop'; $results=@(); "
    script+="foreach ($file in @("+literal+")) { "
    script+="$signature=Get-AuthenticodeSignature -FilePath $file; "
    script+="$signer=$null; if ($signature.SignerCertificate) { $signer=$signature.SignerCertificate.Subject }; "
    script+="$results += [pscustomobject]@{Path=$signature.Path; Status=[string]$signature.Status; Signer=$signer} }; "
    script+="ConvertTo-Json -InputObject @($results) -Compress"
    return powershell_json(script)


def windows_report(distribution,installer,output):
    output=Path(output)
    report=dict(created_utc=datetime.now(timezone.utc).isoformat(),signatures=[],
                defender=dict(status='NotRun',reason='Windows Defender is unavailable on this platform.'),
                limitation='A scan is a time-specific check, not a safety guarantee or a SmartScreen reputation check.')
    if not IS_WINDOWS: return report,False
    paths=[Path(distribution).resolve()/'MellowPDFReader.exe',Path(installer).resolve()]
    try:
        signatures=authenticode(paths)
        report['signatures']=signatures if isinstance(signatures,list) else [signatures]
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        report['signature_error']=str(error)
    try:
        status=powershell_json('Get-MpComputerStatus | Select-Object AMServiceEnabled,AntivirusEnabled,AMEngineVersion,AntivirusSignatureVersion,AntivirusSignatureLastUpdated | ConvertTo-Json -Compress')
        report['defender']['engine']=status
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        report['defender']['reason']='Cannot read Defender status: '+str(error)
        return report,False
    if not status.get('AMServiceEnabled') or not status.get('AntivirusEnabled'):
        report['defender']['reason']='Defender antivirus/service is not enabled on this build runner. No scan was performed.'
        return report,False
    platform_root=Path(os.environ.get('ProgramData','C:/ProgramData'))/'Microsoft/Windows Defender/Platform'
    candidates=sorted(platform_root.glob('*/MpCmdRun.exe'),reverse=True)
    fallback=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Windows Defender/MpCmdRun.exe'
    scanner=next((p for p in candidates+[fallback] if p.is_file()),None)
    if scanner is None:
        report['defender']['reason']='MpCmdRun.exe was not found. No scan was performed.'
        return report,False
    scans=[]
    failed=False
    for name,target in [('app',Path(distribution).resolve()),('installer',Path(installer).resolve())]:
        try:
            # A custom read-only scan checks archives and ignores file exclusions.
            # No remediation, exclusions or Defender preference changes are made.
            result=subprocess.run([str(scanner),'-Scan','-ScanType','3','-File',str(target),'-DisableRemediation'],
                                  capture_output=True,text=True,timeout=240)
            (output/f'defender-{name}.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf8')
            code=result.returncode
            scans.append(dict(target=name,exit_code=code,status='NoThreatsReported' if code==0 else 'DetectionOrScanError'))
            failed|=code!=0
        except (OSError,subprocess.SubprocessError) as error:
            scans.append(dict(target=name,status='ScanError',error=str(error)))
            failed=True
    report['defender'].update(status='DetectionOrScanError' if failed else 'NoThreatsReported',scans=scans,
                              reason='See raw Defender logs. Nonzero scan results block artifact publication.')
    return report,failed


def enforce_release_policy(report, require_signed=False, require_defender=False):
    """Fail closed when a release explicitly requires signing or a real scan."""
    if require_signed:
        signatures=report.get('signatures', [])
        if (report.get('signature_error') or len(signatures)!=2 or
                any(row.get('Status')!='Valid' or not row.get('Signer') for row in signatures)):
            raise ValueError('A signed release requires valid, trusted app and installer signatures.')
    if require_defender and report.get('defender', {}).get('status')!='NoThreatsReported':
        raise ValueError('A release scan is required; Defender must report NoThreatsReported.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--distribution',default='dist/MellowPDFReader')
    parser.add_argument('--installer',default='dist/MellowPDFReader-Setup.exe')
    parser.add_argument('--output',default='dist/build-verification')
    parser.add_argument('--require-signed', action='store_true', help='Reject unsigned, invalid or unavailable app/installer signatures')
    parser.add_argument('--require-defender', action='store_true', help='Reject an unavailable scanner as well as detections/errors')
    args=parser.parse_args()
    # Fingerprint before any scan so missing/quarantined/changed files are detectable.
    manifest=build_manifest(args.distribution,args.installer,args.output)
    report,failed=windows_report(args.distribution,args.installer,args.output)
    root=Path(args.distribution).resolve().parent
    changed=[row['path'] for row in manifest['files'] if not (root/row['path']).is_file() or sha256(root/row['path'])!=row['sha256']]
    report['changed_or_missing_files']=changed
    Path(args.output,'SECURITY.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    enforce_release_policy(report,args.require_signed,args.require_defender)
    print('Defender result:',report['defender']['status'])
    print('Signature status:',[(p.get('Status')) for p in report['signatures']])
    if report['defender']['status']=='NotRun': print(report['defender']['reason'])
    if failed or changed or report.get('signature_error'): raise SystemExit('Verification failed; see SECURITY.json and Defender logs.')


if __name__=='__main__': main()
