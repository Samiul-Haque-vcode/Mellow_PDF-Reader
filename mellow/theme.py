"""Display-only reading tones, using Qt's native raster compositor."""
from functools import lru_cache
import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QImage, QColor, QPainter
from PySide6.QtWidgets import QGraphicsEffect

# Sepia follows the newer eReader reference: one cream field from edge to edge,
# warm brown text, and no contrasting canvas around the original PDF page.
COLORS={'Light':('#ffffff','#f2f2f2'),'Sepia':('#faf1d9','#faf1d9'),
        'Dark':('#242622','#242622'),'Black':('#000000','#000000')}
INK={'Light':'#282d32','Sepia':'#634f38','Dark':'#e8e4d9','Black':'#eeeeee'}
_SRGB=np.arange(256,dtype=np.float32)/255
_LINEAR=np.where(_SRGB<=.04045,_SRGB/12.92,((_SRGB+.055)/1.055)**2.4)


def overlay_colors(theme):
    """Selection/search marks are drawn after toning in source coordinates."""
    dark=normalize_theme(theme) in ('Dark','Black')
    return (QColor(124,181,236,85) if dark else QColor(67,133,190,85),
            QColor(240,190,77,90) if dark else QColor(245,188,45,100),
            QColor('#acd8bd' if dark else '#376c51'))


def normalize_theme(name):
    if name=='Original': return 'Light'
    if name in ('Paper Gray','Rose','Mist','Sage'): return 'Black'
    return name if name in COLORS else 'Sepia'


def tuning_values(value):
    """Validate one theme's small, local controls; malformed metadata is neutral."""
    value=value if isinstance(value,dict) else {}
    def number(key,limit):
        try:return max(-limit,min(limit,int(value.get(key,0))))
        except (ValueError,TypeError,OverflowError):return 0
    return number('warmth',50),number('contrast',30)


def theme_tunings(value):
    value=value if isinstance(value,dict) else {}
    # Carry local tuning preferences forward when the retired palette is saved.
    return {name:dict(zip(('warmth','contrast'),tuning_values(
        value.get(name,value.get('Rose') if name=='Black' else None)))) for name in COLORS}


@lru_cache(maxsize=128)
def tone_colors(theme,warmth=0,contrast=0):
    theme=normalize_theme(theme)
    paper=QColor(COLORS[theme][0]).getRgb()[:3]
    ink=QColor(INK[theme]).getRgb()[:3]
    if theme=='Light':return paper,ink
    if warmth and theme!='Black':
        shift=warmth/50
        paper=tuple(max(0,min(255,round(channel+delta*shift))) for channel,delta in zip(paper,(6,1,-14)))
    if contrast:
        # Positive means stronger contrast: darker light-theme ink / brighter
        # dark-theme ink. Negative remains bounded to retain readable defaults.
        target=(255 if theme in ('Dark','Black') else 0) if contrast>0 else None
        amount=abs(contrast)/100
        ink=tuple(round(channel*(1-amount)+(target if target is not None else background)*amount)
                  for channel,background in zip(ink,paper))
    return paper,ink


def canvas_color(theme,warmth=0,contrast=0):
    theme=normalize_theme(theme)
    if theme=='Light':return COLORS['Light'][1]
    return QColor(*tone_colors(theme,warmth,contrast)[0]).name()


@lru_cache(maxsize=128)
def blend_colors(theme,warmth=0,contrast=0):
    paper,ink=tone_colors(theme,warmth,contrast)
    low,high=(paper,ink) if theme in ('Dark','Black') else (ink,paper)
    # Multiply then Screen: output = low + source * (high-low)/255.
    gain=[max(0,min(255,round((b-a)*255/(255-a)))) for a,b in zip(low,high)]
    return QColor(*gain),QColor(*low)


def recolor(image,theme,preserve=True,warmth=0,contrast=0):
    theme=normalize_theme(theme)
    if theme=='Light' or image.isNull(): return image.copy()
    original=image.convertToFormat(QImage.Format.Format_RGBA8888)
    result=original.copy()
    gain,base=blend_colors(theme,warmth,contrast)
    painter=QPainter(result)
    if theme in ('Dark','Black'):
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Difference)
        painter.fillRect(result.rect(),Qt.GlobalColor.white)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
    painter.fillRect(result.rect(),gain)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
    painter.fillRect(result.rect(),base)
    painter.end()
    source=np.frombuffer(original.constBits(),dtype=np.uint8).reshape(original.height(),original.bytesPerLine())
    source=source[:,:original.width()*4].reshape(original.height(),original.width(),4)
    dest=np.frombuffer(result.bits(),dtype=np.uint8).reshape(result.height(),result.bytesPerLine())
    dest=dest[:,:result.width()*4].reshape(result.height(),result.width(),4)
    # Chromatic pixels remain exact except low-contrast dark-mode ink below.
    # Semitransparent pixels also remain original to avoid compositing fringes.
    mask=source[:,:,3]<255
    if preserve:
        maximum=np.maximum(np.maximum(source[:,:,0],source[:,:,1]),source[:,:,2])
        minimum=np.minimum(np.minimum(source[:,:,0],source[:,:,1]),source[:,:,2])
        chromatic=maximum-minimum>=35
        mask|=chromatic
        if theme in ('Dark','Black'):
            # Preserve readable figure colors exactly. Lift opaque chromatic
            # ink only as much as needed for 4.5:1 against the toned paper.
            # This is a pixel contrast floor, not document-level certification.
            colored=chromatic & (source[:,:,3]==255)
            pixels=source[:,:,:3][colored]
            if pixels.size:
                luminance=_LINEAR[pixels[:,0]]*.2126+_LINEAR[pixels[:,1]]*.7152+_LINEAR[pixels[:,2]]*.0722
                paper=tone_colors(theme,warmth,contrast)[0]
                background=sum(float(_LINEAR[value])*weight for value,weight in zip(paper,(.2126,.7152,.0722)))
                lift=colored.copy()
                lift[colored]=(luminance+.05)/(background+.05)<4.5
                if np.any(lift):
                    linear=_LINEAR[source[:,:,:3][lift]]
                    levels=linear@np.array((.2126,.7152,.0722),dtype=np.float32)
                    target=min(1,4.5*(background+.05)-.05)
                    amount=np.clip((target-levels)/(1-levels),0,1)
                    adjusted=linear+(1-linear)*amount[:,None]
                    srgb=np.where(adjusted<=.0031308,adjusted*12.92,1.055*adjusted**(1/2.4)-.055)
                    dest[:,:,:3][lift]=np.ceil(np.clip(srgb*255,0,255)).astype(np.uint8)
                mask&=~lift
    np.copyto(dest.view(np.uint32).reshape(result.height(),result.width()),
              source.view(np.uint32).reshape(original.height(),original.width()),where=mask)
    return result


class PageTheme(QGraphicsEffect):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.theme='Sepia'
        self.preserve=True
        self.warmth=0
        self.contrast=0
        self._cache_key=None
        self._cache=None
    def clear_cache(self):
        self._cache_key=None
        self._cache=None
    def draw(self,painter):
        offset=QPoint()
        pix=self.sourcePixmap(Qt.CoordinateSystem.LogicalCoordinates,offset)
        if pix.isNull(): return
        if normalize_theme(self.theme)=='Light':
            painter.drawPixmap(offset,pix)
            return
        reader=self.parent()
        key=(pix.cacheKey(),self.theme,self.preserve,self.warmth,self.contrast)
        if key!=self._cache_key:
            original=pix.toImage()
            image=original.copy()
            dpr=pix.devicePixelRatio()
            image.setDevicePixelRatio(dpr)
            target=QPainter(image)
            viewport=reader.viewport().geometry()
            translation=QPointF(viewport.topLeft())-QPointF(reader.horizontalScrollBar().value(),reader.verticalScrollBar().value())
            import math
            for _,page,_ in reader.visible_pages():
                visible=page.translated(translation).intersected(QRectF(viewport))
                if visible.isEmpty(): continue
                visible.translate(-offset.x(),-offset.y())
                pixels=QRect(math.floor(visible.x()*dpr),math.floor(visible.y()*dpr),
                             math.ceil(visible.width()*dpr),math.ceil(visible.height()*dpr))
                toned=recolor(original.copy(pixels),self.theme,self.preserve,self.warmth,self.contrast)
                toned.setDevicePixelRatio(dpr)
                target.drawImage(QPointF(pixels.topLeft())/dpr,toned)
            target.end()
            self._cache_key,self._cache=key,image
        painter.drawImage(offset,self._cache)
        painter.save()
        painter.translate(reader.viewport().pos())
        painter.setClipRect(reader.viewport().rect())
        reader.paint_overlays(painter)
        painter.restore()
