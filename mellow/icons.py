"""Shared toolbar vector icons and application artwork."""
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import Qt,QByteArray,QRectF
from PySide6.QtGui import QIcon,QPixmap,QPainter
from PySide6.QtSvg import QSvgRenderer

ASSETS=Path(__file__).with_name('assets')
PATHS={
 'auto_scroll':'<path d="M5 4h8M5 8h8M5 12h5M17 7v14m-4-4 4 4 4-4"/>',
 'pause':'<path d="M8 5v14M16 5v14"/>',
 'edit':'<path d="m15 4 5 5M4 16 16 4a2 2 0 0 1 4 4L8 20l-5 1Z"/>',
 'home':'<path d="m3 10 9-7 9 7M5 9v12h5v-7h4v7h5V9"/>',
 'open':'<path d="M3 7V5h7l2 3h9v12H3ZM3 10h18"/>',
 'back':'<path d="M21 12H3m6-6-6 6 6 6"/>',
 'forward':'<path d="M3 12h18m-6-6 6 6-6 6"/>',
 'previous':'<path d="m15 5-7 7 7 7"/>',
 'next':'<path d="m9 5 7 7-7 7"/>',
 'minus':'<path d="M5 12h14"/>',
 'plus':'<path d="M5 12h14M12 5v14"/>',
 'search':'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
 'search_results':'<circle cx="8" cy="8" r="4.5"/><path d="m11.5 11.5 3.5 3.5M17 4h4M17 9h4M4 20h17"/>',
 'outline':'<path d="M8 5h13M8 12h13M8 19h13M3 5h.1M3 12h.1M3 19h.1"/>',
 'star':'<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9Z"/>',
 'ruler':'<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 6v5M12 6v3M17 6v5"/>',
 'more':'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
 'menu':'<path d="M4 6h16M4 12h16M4 18h16"/>',
 'settings':'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>',
 'close':'<path d="m6 6 12 12M18 6 6 18"/>',
 'split':'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/>',
 'fullscreen':'<path d="M9 3H3v6M15 3h6v6M3 15v6h6M21 15v6h-6"/>',
 'rotate_left':'<path d="M20 9a8 8 0 0 0-16 0M8 7 4 9 3 5M13 10H7v12h10v-8ZM13 10v4h4"/>',
 'rotate_right':'<path d="M4 9a8 8 0 0 1 16 0M16 7l4 2 1-4M13 10H7v12h10v-8ZM13 10v4h4"/>',
 'extract':'<path d="M14 3H5v18h14V8ZM14 3v5h5M8 12h8M12 12v5m-3-3 3 3 3-3"/>',
 'merge':'<path d="M8 3H3v11h5M16 3h5v11h-5M8 21h8M8 7v5l4 4 4-4V7M12 16v5"/>',
 'images':'<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8" cy="9" r="1.5"/><path d="m3 17 6-5 4 3 4-5 4 5"/>',
 'copy':'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
 'book':'<path d="M12 6C8 3 4 3 2 4v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-3-1-7-1-10 2ZM12 6v15"/>',
 'backup':'<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
}


@lru_cache(maxsize=128)
def icon(name,color='#4d655c'):
    path=PATHS[name]
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
    pixmap=QPixmap(48,48)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter,QRectF(0,0,24,24))
    painter.end()
    return QIcon(pixmap)


def application_icon():
    return QIcon(str(ASSETS/'logo.png'))
