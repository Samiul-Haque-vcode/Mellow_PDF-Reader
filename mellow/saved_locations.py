"""Small metadata helpers; never open or index source documents."""
from collections import Counter
import math
import os
from html import escape


def plain_tooltip(*lines):
    return '<qt>'+'<br>'.join(escape(str(line)).replace('\n','<br>') for line in lines)+'</qt>'


def path_key(path):
    # Follow the host's case rules without probing every file on disk.
    return os.path.normcase(os.path.abspath(os.path.normpath(str(path))))


def destination_key(row):
    """Source anchors rounded to 0.01 PDF point; titles/printed labels may differ."""
    try:
        page=row['page']
        if isinstance(page,bool) or not isinstance(page,int) or page<0:return None
        x,y=float(row.get('x',0)),float(row.get('y',0))
        if not math.isfinite(x) or not math.isfinite(y):return None
        return row.get('kind'),path_key(row['path']),page,round(x,2),round(y,2)
    except (KeyError,TypeError,ValueError,OverflowError):
        return None


def destination_counts(rows):
    return Counter(key for row in rows if (key:=destination_key(row)) is not None)


def rewrite_paths(value,old,new):
    """Rewrite document fields, including nested navigation states, not titles."""
    original=path_key(old)
    def rewrite(item):
        if isinstance(item,list):return [rewrite(part) for part in item]
        if not isinstance(item,dict):return item
        return {key:(new if key in ('path','active_path') and isinstance(part,str)
                    and path_key(part)==original else rewrite(part)) for key,part in item.items()}
    return rewrite(value)


def document_paths(value):
    if isinstance(value,list):
        for part in value:yield from document_paths(part)
    elif isinstance(value,dict):
        for key,part in value.items():
            if key in ('path','active_path') and isinstance(part,str):yield part
            else:yield from document_paths(part)
