"""Small OS integration helpers; paths are arguments, never shell commands."""
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import QUrl,QUrlQuery
from PySide6.QtGui import QDesktopServices


def show_in_folder(path):
    path=Path(path).resolve()
    if not path.exists(): raise FileNotFoundError(f'File not found:\n{path}')
    if sys.platform=='win32':
        subprocess.Popen([explorer_executable(),'/select,',str(path)])
        return True
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


def open_external_link(url):
    """Only ordinary web/email links from untrusted PDFs reach the OS handler."""
    url=QUrl(url)
    if not url.isValid():return False
    scheme=url.scheme().lower()
    if scheme in ('http','https'):
        if not url.host() or url.userInfo():return False
    elif scheme=='mailto':
        if not url.path() or any(ord(c)<32 for c in url.path()):return False
        query=QUrlQuery(url)
        if any(key.lower() in ('attach','attachment') for key,value in query.queryItems()):return False
    else:return False
    return QDesktopServices.openUrl(url)


def explorer_executable():
    """Resolve Windows Explorer through the OS, never the working directory/PATH."""
    import ctypes
    buffer=ctypes.create_unicode_buffer(32768)
    count=ctypes.WinDLL('kernel32',use_last_error=True).GetWindowsDirectoryW(buffer,len(buffer))
    if count==0 or count>=len(buffer):raise OSError('Cannot locate the Windows directory')
    return str(Path(buffer.value)/'explorer.exe')
