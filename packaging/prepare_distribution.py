"""Remove the optional Mesa OpenGL fallback from this CPU/raster Widgets app."""
import argparse
from pathlib import Path


def prepare(distribution):
    root=Path(distribution)
    if not (root/'MellowPDFReader.exe').is_file():
        raise ValueError('Choose the PyInstaller MellowPDFReader application folder.')
    # Mellow uses QWidget/QPainter and Qt PDF raster rendering. It has no
    # QOpenGLWidget, Qt Quick or browser view requiring this optional renderer.
    removed=[]
    for relative in ('_internal/PySide6/opengl32sw.dll','_internal/PySide6/Qt/bin/opengl32sw.dll'):
        path=root/relative
        if path.is_file():
            size=path.stat().st_size;path.unlink()
            removed.append(dict(path=relative,bytes=size))
    return removed


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('distribution')
    for item in prepare(parser.parse_args().distribution):
        print('Removed optional software OpenGL renderer:',item['path'],item['bytes'],'bytes')
