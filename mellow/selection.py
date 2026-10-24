"""Text-layer selection with page-coordinate ranges, never OCR or PDF edits."""
from collections import OrderedDict
from PySide6.QtCore import QPointF


class TextSelection:
    def __init__(self,document):
        self.document=document
        self.anchor=None
        self.ranges={}
        self._full=OrderedDict()
        self._parts=OrderedDict()
    def clear(self):
        self.anchor=None
        self.ranges={}
        self._parts.clear()
    def set_document(self,document):
        self.clear()
        self._full.clear()
        self.document=document
    def full(self,page):
        if page not in self._full:
            self._full[page]=self.document.getAllText(page)
            if len(self._full)>4: self._full.popitem(last=False)
        self._full.move_to_end(page)
        return self._full[page]
    def caret(self,page,point,near_only=False):
        full=self.full(page)
        bounds=[polygon.boundingRect() for polygon in full.bounds()]
        if not full.text() or not bounds: return None
        def distance(rect):
            dx=max(rect.left()-point.x(),0,point.x()-rect.right())
            dy=max(rect.top()-point.y(),0,point.y()-rect.bottom())
            return dx*dx+dy*dy*4
        rect=min(bounds,key=distance)
        if near_only and distance(rect)>24**2: return None
        x=max(rect.left(),min(rect.right(),point.x()))
        y=rect.center().y()
        # Prefix/suffix selections expose native character indices. Using the
        # source line also handles drags ending in whitespace beside the text.
        prefix=self.document.getSelection(page,QPointF(rect.left(),y),QPointF(x,y))
        if prefix.isValid() and prefix.text(): return prefix.endIndex()
        suffix=self.document.getSelection(page,QPointF(x,y),QPointF(rect.right(),y))
        if suffix.isValid() and suffix.text(): return suffix.startIndex()
        return None
    def begin(self,page,point,extend=False):
        index=self.caret(page,point,near_only=True)
        if index is None:
            if not extend: self.clear()
            return False
        if not extend or self.anchor is None:
            self.clear()
            self.anchor=(page,index)
        else: self.select_to(page,point)
        return True
    def select_to(self,page,point):
        if self.anchor is None: return
        index=self.caret(page,point)
        if index is None:
            # Image-only pages contribute no text, but a cross-page drag can
            # still include selectable pages before or after them.
            index=0
        self.set_extent(page,index)
    def set_extent(self,page,index):
        if self.anchor is None: return
        first,last=sorted((self.anchor,(page,index)))
        ranges={}
        for number in range(first[0],last[0]+1):
            start=first[1] if number==first[0] else 0
            end=last[1] if number==last[0] else None
            if end is None or end>start: ranges[number]=(start,end)
        self.ranges=ranges
        self._parts.clear()
    def page(self,page):
        limits=self.ranges.get(page)
        if limits is None: return None
        key=(page,limits)
        if key not in self._parts:
            start,end=limits
            if end is None: end=self.full(page).endIndex()
            self._parts[key]=self.document.getSelectionAtIndex(page,start,max(0,end-start))
            if len(self._parts)>4: self._parts.popitem(last=False)
        return self._parts[key]
    def page_text(self,page,join_paragraphs=False):
        part=self.page(page)
        if not part or not part.text():return ''
        full=self.full(page)
        limits=self.ranges[page]
        lines=column_text(self.document,page,part,structured=True) if limits[0]<=full.startIndex() and (limits[1] is None or limits[1]>=full.endIndex()) else None
        text=clean_text('\n'.join(line[1] for line in lines) if lines is not None else part.text())
        if join_paragraphs:
            if lines is None:lines=selection_lines(self.document,page,part)
            text=join_paragraph_lines(text,lines)
        return text
    def text(self,join_paragraphs=False):
        chunks=[text for page in sorted(self.ranges) if (text:=self.page_text(page,join_paragraphs))]
        return ('\n\n' if join_paragraphs else '\n').join(chunks)
    def select_page(self,page):
        full=self.full(page)
        self.clear()
        if full.text():
            self.anchor=(page,full.startIndex())
            self.ranges[page]=(full.startIndex(),full.endIndex())
    def select_word(self,page,point):
        index=self.caret(page,point,near_only=True)
        if index is None: self.clear(); return
        limit=self.full(page).endIndex()
        def char(i):
            if not 0<=i<limit: return ''
            return self.document.getSelectionAtIndex(page,i,1).text()
        def word(i):
            value=char(i)
            return bool(value) and (value.isalnum() or value in "_'-’")
        if not word(index) and word(index-1): index-=1
        if not word(index): self.clear(); return
        first,last=index,index+1
        while word(first-1): first-=1
        while word(last): last+=1
        self.anchor=(page,first)
        self.set_extent(page,last)


def clean_text(text):
    """Expand text ligatures without flattening scientific superscripts/symbols."""
    import unicodedata
    for glyph,replacement in {'ﬀ':'ff','ﬁ':'fi','ﬂ':'fl','ﬃ':'ffi','ﬄ':'ffl','ﬅ':'st','ﬆ':'st'}.items():text=text.replace(glyph,replacement)
    return unicodedata.normalize('NFC',text.replace('\r\n','\n').replace('\r','\n').replace('\u00ad',''))


def column_text(document,page,selection,structured=False):
    """Conservative full-page column ordering; ambiguous layouts retain PDF order.

    Require multiple prose lines on each side of a genuine empty gutter. This
    intentionally leaves tables, short formulas and partial selections alone.
    """
    bounds=selection.bounds()
    if not 6<=len(bounds)<=2000:return None
    lines=[]
    for polygon in bounds:
        rect=polygon.boundingRect()
        part=document.getSelection(page,QPointF(rect.left()+.1,rect.center().y()),QPointF(rect.right()-.1,rect.center().y()))
        if not part.isValid() or not part.text():continue
        lines.append((rect,part.text(),part.startIndex(),part.endIndex()))
    if len(lines)!=len(bounds):return None
    groups=[]
    for line in sorted(lines,key=lambda line:line[0].left()):
        if groups and abs(groups[-1][0][0].left()-line[0].left())<18:groups[-1].append(line)
        else:groups.append([line])
    dominant=sorted(groups,key=len,reverse=True)[:2]
    if len(dominant)<2 or min(map(len,dominant))<3:return None
    left,right=sorted(dominant,key=lambda group:group[0][0].left())
    left_edges=[line[0].right() for line in left if line[0].width()<document.pagePointSize(page).width()*.6]
    if not left_edges:return None
    gutter=right[0][0].left()-max(left_edges)
    if gutter<24 or right[0][0].left()-left[0][0].left()<document.pagePointSize(page).width()*.25:return None
    if any(sum(len(line[1].split())>=4 for line in group)<len(group)*.6 for group in (left,right)):return None
    middle=(max(left_edges)+right[0][0].left())/2
    top=max(min(line[0].top() for line in group) for group in (left,right))
    bottom=min(max(line[0].bottom() for line in group) for group in (left,right))
    before=[];after=[];body=[]
    for line in lines:
        rect=line[0]
        if rect.bottom()<top:before.append(line)
        elif rect.top()>bottom:after.append(line)
        elif rect.left()<middle<rect.right():return None
        else:body.append(line)
    # Never lose characters when Qt's line rectangles overlap or omit content.
    source=''.join(selection.text().split())
    found=''.join(''.join(line[1].split()) for line in sorted(lines,key=lambda line:line[2]))
    if source!=found:return None
    order=sorted(before,key=lambda line:(line[0].top(),line[0].left()))
    order+=sorted(body,key=lambda line:(line[0].left()>middle,line[0].top(),line[0].left()))
    order+=sorted(after,key=lambda line:(line[0].top(),line[0].left()))
    return order if structured else '\n'.join(line[1] for line in order)


def selection_lines(document,page,selection):
    """Map native text lines by verified character ranges, not mouse hit testing.

    A PDF line may contain several font runs. Treating each run as a new line
    creates spurious breaks; character ranges keep those runs together. Reject
    ambiguous indices or a logical line spanning several visual baselines.
    """
    import statistics
    from PySide6.QtCore import QRectF
    raw=selection.text()
    if selection.endIndex()-selection.startIndex()!=len(raw):return None
    source_lines=raw.splitlines(keepends=True)
    if not 1<=len(source_lines)<=2000:return None
    lines=[];offset=selection.startIndex();paragraph=False
    for raw_line in source_lines:
        text=raw_line.rstrip('\r\n')
        start=offset;offset+=len(raw_line)
        if not text.strip():paragraph=bool(lines);continue
        part=document.getSelectionAtIndex(page,start,len(text))
        if not part.isValid() or part.text()!=text:return None
        bounds=[polygon.boundingRect() for polygon in part.bounds() if not polygon.isEmpty()]
        if not bounds:return None
        height=statistics.median(rect.height() for rect in bounds)
        if max(rect.center().y() for rect in bounds)-min(rect.center().y() for rect in bounds)>height*.65:return None
        rect=QRectF(bounds[0])
        for bound in bounds[1:]:rect=rect.united(bound)
        lines.append((rect,text,start,start+len(text),paragraph))
        paragraph=False
    return lines or None


def join_paragraph_lines(text,lines=None):
    """Join clearly wrapped prose, never guess at an ambiguous PDF layout.

    No dehyphenation, symbol normalization or equation/table reconstruction.
    Geometry preserves indents, paragraph gaps and column/page boundaries.
    """
    import re
    import statistics
    if not lines:return text
    if ''.join(clean_text(''.join(line[1] for line in lines)).split())!=''.join(text.split()):return text
    def prose(value,short_tail=False):
        value=value.strip()
        if re.match(r'(?:[•●▪*–—-]|\d+[.)]|[A-Za-z][.)])\s',value):return False
        if any(char in value for char in '=+∑∫√≈≤≥→|−×÷≠≡±∂∞∏∇\t'):return False
        if re.search(r'\S[ ]{2,}\S',value):return False
        words=value.split()
        # Short captions, numeric rows and formulas stay as separate lines.
        ordinary=(sum(any(c.isalpha() for c in word) for word in words)>=len(words)*.8
                  and sum(word[:1].islower() for word in words)>=len(words)*.6)
        if short_tail:
            # A short sentence ending can finish a long wrapped line, but
            # cannot itself start a chain joining unrelated short rows.
            return (2<=len(words)<5 and ordinary and value[:1].islower()
                    and value.endswith(('.', '!', '?')))
        return len(words)>=5 and ordinary
    height=statistics.median(line[0].height() for line in lines)
    steps=[right[0].top()-left[0].top() for left,right in zip(lines,lines[1:])
           if abs(right[0].left()-left[0].left())<=max(4,height*.3)
           and height*.5<right[0].top()-left[0].top()<height*3]
    # Glyph ink bounds can be much shorter than a font's normal line spacing.
    # Measure the document's own pitch before classifying a gap as a paragraph.
    # Paragraph gaps must not inflate the pitch in sparse selections. Prefer
    # the smallest plausible observed spacing; an unusually tight line can
    # conservatively prevent joining, rather than merge separate paragraphs.
    pitch=min(steps) if steps else height*1.4
    output=clean_text(lines[0][1]).strip()
    for previous,current in zip(lines,lines[1:]):
        before,after=previous[0],current[0]
        left,right=clean_text(previous[1]).strip(),clean_text(current[1]).strip()
        gap=after.top()-before.bottom()
        aligned=abs(after.left()-before.left())<=max(4,height*.3)
        following=0<after.top()-before.top()<=pitch*1.4 and gap>=-.25*height
        left_prose,right_prose=prose(left),prose(right)
        both_prose=left_prose and right_prose
        wrapped=left_prose and (right_prose or prose(right,short_tail=True)) and not left.endswith((':',';','-','–','—'))
        separator=' ' if aligned and following and wrapped else '\n'
        # Large gaps and a new indented block are paragraph boundaries, even
        # if another geometric condition already rejected joining.
        if both_prose and after.top()>before.top() and (after.top()-before.top()>pitch*1.4 or after.left()-before.left()>height*.6):separator='\n\n'
        if len(current)>4 and current[4]:separator='\n\n'
        output+=separator+right
    return output
