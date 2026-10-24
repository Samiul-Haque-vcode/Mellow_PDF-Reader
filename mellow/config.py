from pathlib import Path
import sys
from PySide6.QtCore import QStandardPaths


def fullscreen_hide_delay(value=600):
    """Stored milliseconds; malformed preferences keep the established default."""
    try:
        if isinstance(value,bool):return 600
        return max(200,min(5000,int(value)))
    except (TypeError,ValueError,OverflowError):
        return 600


def data_directory(portable=False,executable=None):
    if executable is None:
        executable=Path(sys.executable) if getattr(sys,'frozen',False) else Path(__file__).resolve().parent.parent/'run_mellow.py'
    base=Path(executable).resolve().parent
    if portable or (base/'portable.ini').exists():
        return base/'mellow-data'
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
