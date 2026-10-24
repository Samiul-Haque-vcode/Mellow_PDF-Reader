"""Small OS integration helpers; paths are arguments, never shell commands."""
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def show_in_folder(path):
    path=Path(path).resolve()
    if not path.exists(): raise FileNotFoundError(f'File not found:\n{path}')
    if sys.platform=='win32':
        subprocess.Popen(['explorer.exe','/select,',str(path)])
        return True
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
