"""Collect real installed notices, application license and an auditable inventory."""
import argparse
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys
import sysconfig

ROOT=Path(__file__).resolve().parents[1]
PACKAGES=('PySide6','PySide6_Essentials','PySide6_Addons','PySide6_Pdf',
          'shiboken6','numpy','pypdf','pyinstaller')


def collect(distribution, root=ROOT):
    output=Path(distribution)/'licenses'
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
    review=dict(packages=inventory,python=sys.version.split()[0],
                python_notice_collected=python_license is not None,
                missing_package_notice_files=[row['name'] for row in inventory if not row['notices']],
                complete_attribution_review=False,
                remaining='Review exact bundled Qt/PDFium and native-library notices before public release. Package metadata alone does not supply all third-party terms.')
    (output/'DEPENDENCIES.json').write_text(json.dumps(review,indent=2),encoding='utf8')
    (output/'DEPENDENCIES.md').write_text('\n'.join(lines),encoding='utf8')
    for source in (root/'packaging/notices').glob('*'):
        if source.is_file():shutil.copy2(source,output/source.name)
    for name in ('README.md','LICENSE','THIRD_PARTY.md'):
        shutil.copy2(root/name,output.parent/name)
    return review


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('distribution')
    collect(parser.parse_args().distribution)
