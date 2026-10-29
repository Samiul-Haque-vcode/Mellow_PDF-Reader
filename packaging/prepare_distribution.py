"""Prune unused Mesa and optional Qt TLS components with import checks."""
import argparse
from pathlib import Path


def prepare(distribution):
    root=Path(distribution)
    if not (root/'MellowPDFReader.exe').is_file():
        raise ValueError('Choose the PyInstaller MellowPDFReader application folder.')
    # Mellow uses QWidget/QPainter and Qt PDF raster rendering. It has no
    # QOpenGLWidget, Qt Quick or browser view requiring this optional renderer.
    candidates=[root/relative for relative in
        ('_internal/PySide6/opengl32sw.dll','_internal/PySide6/Qt/bin/opengl32sw.dll')]
    tls=[root/'_internal/PySide6/plugins/tls/qopensslbackend.dll',
         root/'_internal/libssl-3-x64.dll',root/'_internal/libcrypto-3-x64.dll']
    if all(path.is_file() for path in tls):
        # Windows Qt retains its native Schannel backend. The optional OpenSSL
        # plugin brings a second SSL build; CPython's current SSL DLLs remain.
        # Refuse pruning if any other binary imports either optional DLL.
        import pefile
        excluded=set(tls)
        for path in root.rglob('*'):
            if not path.is_file() or path in excluded or path.suffix.lower() not in ('.dll','.pyd'):continue
            pe=pefile.PE(str(path),fast_load=True)
            try:
                pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT'],
                    pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT']])
                entries=getattr(pe,'DIRECTORY_ENTRY_IMPORT',[])+getattr(pe,'DIRECTORY_ENTRY_DELAY_IMPORT',[])
                if any(entry.dll.lower() in (b'libssl-3-x64.dll',b'libcrypto-3-x64.dll') for entry in entries):
                    raise ValueError('Cannot remove the optional TLS backend: another bundled binary needs its SSL libraries: '+path.name)
            finally:pe.close()
        candidates.extend(tls)
    removed=[]
    for path in candidates:
        if path.is_file():
            size=path.stat().st_size;path.unlink()
            removed.append(dict(path=path.relative_to(root).as_posix(),bytes=size))
    return removed


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('distribution')
    for item in prepare(parser.parse_args().distribution):
        print('Removed unused distribution component:',item['path'],item['bytes'],'bytes')
