"""Small validated per-file preferences; source PDFs are never rewritten."""
import math


def crop_values(value):
    if not isinstance(value,(list,tuple)) or len(value)!=4:
        raise ValueError('Choose four page margins.')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not 0<=v<=40 or not math.isfinite(v) for v in value):
        raise ValueError('Margins must be between 0 and 40 percent.')
    return tuple(float(v) for v in value)


def numbering_values(value):
    if value is None:return None
    if not isinstance(value,dict) or set(value)!={'pdf','book'}:
        raise ValueError('Choose a PDF page and its book page number.')
    if type(value['pdf']) is not int or not 0<=value['pdf']<1_000_000:
        raise ValueError('Invalid PDF page.')
    if type(value['book']) is not int or not 1<=value['book']<=1_000_000:
        raise ValueError('Book page numbers must be positive.')
    return dict(value)


def page_label(document,page):
    mapping=getattr(document,'_mellow_numbering',None)
    native=document.pageLabel(page) or str(page+1)
    if mapping:
        if page>=mapping['pdf']:return str(mapping['book']+page-mapping['pdf'])
        # Numeric front matter would collide with the custom book numbering.
        return '#'+str(page+1) if native.isdecimal() else native
    return native


def page_index(document,text):
    text=text.strip()
    if text.startswith('#'):
        try:return int(text[1:])-1
        except ValueError:return -1
    mapping=getattr(document,'_mellow_numbering',None)
    if mapping and text.isdecimal():
        number=int(text)-mapping['book']+mapping['pdf']
        return number if number>=mapping['pdf'] else -1
    native=document.pageIndexForLabel(text)
    if mapping:return native if 0<=native<mapping['pdf'] else -1
    return native if native>=0 else (int(text)-1 if text.isdecimal() else -1)
