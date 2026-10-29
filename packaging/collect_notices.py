"""Collect real installed notices, application license and an auditable inventory."""
import argparse
import importlib.metadata as metadata
import json
import hashlib
import platform
from pathlib import Path
import shutil
import sys
import sysconfig

ROOT=Path(__file__).resolve().parents[1]
PACKAGES=('PySide6_Essentials','PySide6_Pdf',
          'shiboken6','numpy','pypdf','pyinstaller')

REVIEW_CHECKS=('qt_pdf_source_match','qt_runtime_notices','native_library_notices','lgpl_source_access')
PDF_NOTICES={'abseil','freetype','pdfium','the-chromium-project','fast-float','icu','libjpeg-turbo','libpng','zlib'}


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def notice_path(folder,name):
    if not isinstance(name,str) or not name or '\\' in name:
        raise ValueError('Invalid notice path.')
    path=Path(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Notice paths must stay inside the licenses folder.')
    result=folder/path
    if not result.resolve().is_relative_to(folder.resolve()) or not result.is_file():
        raise ValueError('Missing or unsafe notice file: '+name)
    return result


def small_json(path):
    with Path(path).open('rb') as source:body=source.read(2*1024*1024+1)
    if len(body)>2*1024*1024:raise ValueError('Notice manifest exceeds 2 MB.')
    return json.loads(body)


def pdf_notice_status(output,versions):
    try:
        data=small_json(output/'qt-pdf-manifest.json')
        if type(data.get('format')) is not int or data.get('format')!=1 or data.get('distribution')!='PySide6_Pdf':
            raise ValueError('Invalid Qt PDF notice manifest.')
        if not versions.get('PySide6_Pdf') or data.get('distribution_version')!=versions['PySide6_Pdf']:
            raise ValueError('Qt PDF notices do not match the installed distribution version.')
        documents=data['documents']
        if not isinstance(documents,list) or len(documents)!=len(PDF_NOTICES):
            raise ValueError('Qt PDF notice list is incomplete.')
        expected={f"qt-pdf-{data['qt_pdf_version']}/{name}.txt" for name in PDF_NOTICES}
        if {row['path'] for row in documents}!=expected:
            raise ValueError('Qt PDF notice components are missing or duplicated.')
        for row in documents:
            if not isinstance(row['sha256'],str) or digest(notice_path(output,row['path']))!=row['sha256']:
                raise ValueError('Qt PDF notice hash mismatch: '+row['path'])
        return dict(valid=True,version=data['qt_pdf_version'],documents=len(documents))
    except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError) as error:
        return dict(valid=False,reason=str(error))


def reviewed_notices(output,versions,native_files):
    """Verify recorded review evidence; this does not perform a legal review."""
    try:
        data=small_json(output/'REVIEW.json')
        if type(data.get('format')) is not int or data.get('format')!=1 or data.get('package_versions')!=versions:
            raise ValueError('Attribution review is missing or does not match installed packages.')
        if data.get('python')!=sys.version.split()[0] or data.get('platform')!=sys.platform or data.get('architecture')!=platform.machine():
            raise ValueError('Attribution review does not match this Python/platform/architecture.')
        if not native_files or data.get('native_files')!=native_files:
            raise ValueError('Attribution review does not match the bundled native files.')
        files=data['files']
        if not isinstance(files,dict) or not files:raise ValueError('Review evidence is missing.')
        for name,expected in files.items():
            if not isinstance(expected,str) or digest(notice_path(output,name))!=expected:
                raise ValueError('Review evidence hash mismatch: '+name)
        checks=data['checks']
        if set(checks)!=set(REVIEW_CHECKS):raise ValueError('Required review checks are missing.')
        for name in REVIEW_CHECKS:
            check=checks[name]
            if not isinstance(check,dict) or check.get('complete') is not True or not isinstance(check.get('evidence'),list) or not check['evidence'] or not set(check['evidence'])<=files.keys():
                raise ValueError('Review check needs completed evidence: '+name)
        packages=data['package_notices']
        if set(packages)!=set(versions):raise ValueError('Package notice mappings are incomplete.')
        if any(not isinstance(names,list) or not names or not set(names)<=files.keys() for names in packages.values()):
            raise ValueError('Package notices need hashed review evidence.')
        return dict(valid=True,checks=list(REVIEW_CHECKS),package_notices=packages)
    except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError) as error:
        return dict(valid=False,reason=str(error),required_checks=list(REVIEW_CHECKS))


def require_complete(report):
    if not report['complete_attribution_review']:
        raise ValueError('Binary distribution is not ready:\n- '+'\n- '.join(report['collection_issues']))


def collect(distribution, root=ROOT):
    output=Path(distribution)/'licenses'
    if output.is_symlink():raise ValueError('The license output folder must not be a symbolic link.')
    output.mkdir(parents=True,exist_ok=True)
    root=Path(root)
    inventory=[]
    lines=['# Bundled dependency inventory','',
           'Mellow source is MIT-licensed. Dependencies keep their own terms.',
           'PyInstaller is a build tool; its bootloader is distributed with the app.',
           'Qt PDF embeds PDFium and other components; see Qt-PDF-LICENSES.txt.',
           'This inventory is evidence, not a declaration of complete attribution.','']
    for name in PACKAGES:
        try: dist=metadata.distribution(name)
        except metadata.PackageNotFoundError: continue
        urls=dist.metadata.get_all('Project-URL',[])
        license_name=dist.metadata.get('License-Expression',dist.metadata.get('License','See package/source license'))
        row=dict(name=name,version=dist.version,license=license_name,urls=urls,notices=[])
        lines.extend([f'## {name} {dist.version}',license_name,*urls])
        for item in dist.files or []:
            if any(term in str(item).lower() for term in ('license','copying','notice','copyright')):
                source=Path(dist.locate_file(item))
                if source.is_file():
                    dest=output/name/str(item).replace('..','parent')
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,dest)
                    row['notices'].append(dest.relative_to(output).as_posix())
        inventory.append(row)
        lines.append('')
    python_candidates=[Path(sys.base_prefix)/'LICENSE.txt',
                       Path(sysconfig.get_path('stdlib'))/'LICENSE.txt',
                       Path(sys.base_prefix)/'LICENSE']
    python_license=next((p for p in python_candidates if p.is_file()),None)
    if python_license:
        shutil.copy2(python_license,output/'Python-LICENSE.txt')
    notices=root/'packaging/notices'
    for source in notices.rglob('*'):
        if not source.is_file():continue
        relative=source.relative_to(notices)
        if source.is_symlink() or not source.resolve().is_relative_to(notices.resolve()):
            raise ValueError('Notice sources must not link outside the notice folder.')
        target=output/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
    versions={row['name']:row['version'] for row in inventory}
    native_files={path.relative_to(output.parent).as_posix():digest(path)
                  for path in sorted(output.parent.rglob('*')) if path.is_file()
                  and path.relative_to(output.parent).as_posix().casefold()!='mellowpdfreader.exe'
                  and (path.suffix.lower() in ('.dll','.pyd','.so','.exe') or '.so.' in path.name)}
    pdf_status=(pdf_notice_status(output,versions) if (notices/'qt-pdf-manifest.json').is_file()
                else dict(valid=False,reason='qt-pdf-manifest.json is missing from the source notice folder.'))
    recorded_review=(reviewed_notices(output,versions,native_files) if (notices/'REVIEW.json').is_file()
                     else dict(valid=False,reason='REVIEW.json is missing from the source notice folder.',required_checks=list(REVIEW_CHECKS)))
    if recorded_review['valid']:
        for row in inventory:
            row['notices']=sorted(set(row['notices']+recorded_review['package_notices'][row['name']]))
    missing_packages=sorted(set(PACKAGES)-versions.keys())
    missing_notices=[row['name'] for row in inventory if not row['notices']]
    issues=[]
    if missing_packages:issues.append('Required packages not installed: '+', '.join(missing_packages))
    if missing_notices:issues.append('Package notices need coverage: '+', '.join(missing_notices))
    if python_license is None:issues.append('Python license was not collected.')
    if not pdf_status['valid']:issues.append('Qt PDF notices: '+pdf_status['reason'])
    if not recorded_review['valid']:issues.append('Recorded distribution review: '+recorded_review['reason'])
    review=dict(packages=inventory,python=sys.version.split()[0],
                python_notice_collected=python_license is not None,
                missing_required_packages=missing_packages,
                missing_package_notice_files=missing_notices,
                qt_pdf_notices=pdf_status,recorded_review=recorded_review,
                native_files=native_files,collection_issues=issues,
                complete_attribution_review=not issues,
                remaining='Complete the listed checks before binary redistribution. A valid evidence manifest records a maintainer review; it does not automatically establish legal compliance.')
    (output/'DEPENDENCIES.json').write_text(json.dumps(review,indent=2),encoding='utf8')
    (output/'DEPENDENCIES.md').write_text('\n'.join(lines),encoding='utf8')
    for name in ('README.md','LICENSE','THIRD_PARTY.md'):
        shutil.copy2(root/name,output.parent/name)
    return review


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('distribution')
    parser.add_argument('--require-complete',action='store_true',help='Fail if notice collection or recorded distribution review is incomplete')
    args=parser.parse_args()
    report=collect(args.distribution)
    print('Attribution review:', 'complete' if report['complete_attribution_review'] else 'incomplete')
    for issue in report['collection_issues']:print('- '+issue)
    if args.require_complete:
        try:require_complete(report)
        except ValueError as error:parser.exit(2,str(error)+'\n')
