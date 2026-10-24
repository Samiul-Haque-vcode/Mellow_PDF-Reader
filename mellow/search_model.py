"""Incremental search filtering over Qt PDF's native source-coordinate results."""
import time
import unicodedata
import re
from collections import OrderedDict
from PySide6.QtCore import QAbstractListModel,QModelIndex,QTimer,Qt,Signal,QPointF
from PySide6.QtPdf import QPdfSearchModel,QPdfLink


def word_character(char):
    return bool(char) and (char.isalnum() or char=='_' or unicodedata.category(char).startswith('M'))


class SearchModel(QAbstractListModel):
    searchStringChanged=Signal()
    statusChanged=Signal()
    optionsChanged=Signal()
    Status=QPdfSearchModel.Status

    def __init__(self,parent=None):
        super().__init__(parent)
        self.native=QPdfSearchModel(self)
        self._document=None
        self.whole_words=False
        self.match_case=False
        self._rows=[]
        self._excerpts=OrderedDict()
        self._cursor=0
        self._status=self.Status.Null
        self._waiting_native=False
        self._paused=False
        self.timer=QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.pump)
        self.native.rowsInserted.connect(self.schedule)
        self.native.modelReset.connect(self.reset_results)
        self.native.statusChanged.connect(self.schedule)
        self.native.searchStringChanged.connect(self.searchStringChanged)

    def document(self):return self._document
    def setDocument(self,document):
        self.timer.stop()
        self._document=document
        self._waiting_native=bool(document and self.searchString())
        self.native.setDocument(document)
        self.reset_results()
    def searchString(self):return self.native.searchString()
    def setSearchString(self,text):
        if text!=self.searchString():
            self._waiting_native=bool(text and self._document)
            self.native.setSearchString(text)
    def status(self):return self._status
    def set_paused(self,paused):
        if self._paused==bool(paused):return
        self._paused=bool(paused)
        if self._paused:self.timer.stop()
        else:self.schedule()
    def set_status(self,status):
        if self._status!=status:
            self._status=status
            self.statusChanged.emit()
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self._rows)
    def resultAtIndex(self,index):
        if not 0<=index<len(self._rows):return QPdfLink()
        return self.native.resultAtIndex(self._rows[index])
    def resultsOnPage(self,page):
        # Native results are in page order. Binary search avoids scanning an
        # entire book for each painted page, without another copy of the links.
        import bisect
        first=bisect.bisect_left(self._rows,page,key=lambda row:self.native.resultAtIndex(row).page())
        last=bisect.bisect_right(self._rows,page,key=lambda row:self.native.resultAtIndex(row).page())
        return [self.native.resultAtIndex(row) for row in self._rows[first:last]]
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0<=index.row()<len(self._rows):return None
        result=self.resultAtIndex(index.row())
        if role in (Qt.ItemDataRole.DisplayRole,Qt.ItemDataRole.ToolTipRole):
            from .reading_options import page_label
            label=page_label(self._document,result.page())
            details=f'Page {label}'
            if label!=str(result.page()+1):details+=f' · PDF page {result.page()+1}'
            row=self._rows[index.row()]
            if row not in self._excerpts:
                self._excerpts[row]=self.excerpt(result)
                if len(self._excerpts)>128:self._excerpts.popitem(last=False)
            self._excerpts.move_to_end(row)
            return details+'\n'+self._excerpts[row]
        return None
    def excerpt(self,result):
        """Read a bounded, verified source range only for requested result rows.

        Native snippet offsets can cut words or omit a title's context. Keep
        the actual match spelling; don't substitute the user's query casing.
        Broken mappings fall back to native context without guessing glyphs.
        """
        source=self.source_match(result)
        spelling=source[0] if source else self.searchString()
        before,after=result.contextBefore(),result.contextAfter()
        # Keep the match near the beginning of the compact visible excerpt.
        leading,trailing=len(before)>40,len(after)>110
        if source and source[1] is not None:
            _,first,last=source
            start=max(0,first-40)
            part=self._document.getSelectionAtIndex(result.page(),start,last-start+110)
            text=part.text();offset=first-start;end=last-start
            if (part.isValid() and part.startIndex()==start
                    and ' '.join(text[offset:end].split())==spelling):
                before,after=text[:offset],text[end:]
                leading=start>0
                trailing=part.endIndex()>=last+110
        before,after=before[-40:],after[:110]
        # Clip context at whitespace rather than displaying orphan word tails.
        # Keep adjacency at the match itself (self-attention, cat2, etc.).
        if leading and re.search(r'\s',before):before=re.split(r'\s',before,maxsplit=1)[1]
        if trailing and re.search(r'\s',after):after=after.rsplit(None,1)[0] if after.strip() else ''
        value=('…' if leading else '')+before+spelling+after+('…' if trailing else '')
        return ' '.join(''.join(char if char.isprintable() and char!='⏎' else ' ' for char in value).split())
    def set_options(self,whole_words=None,match_case=None):
        whole=self.whole_words if whole_words is None else bool(whole_words)
        case=self.match_case if match_case is None else bool(match_case)
        if (whole,case)==(self.whole_words,self.match_case):return
        self.whole_words,self.match_case=whole,case
        self.reset_results()
        self.optionsChanged.emit()
    def reset_results(self,*_):
        self.timer.stop()
        self.beginResetModel()
        self._rows=[];self._cursor=0
        self._excerpts.clear()
        self.endResetModel()
        self.schedule()
    def schedule(self,*_):
        if not self._document or not self.searchString():
            self.set_status(self.Status.Null)
            return
        if self.native.status()==self.Status.Searching:self._waiting_native=False
        self.set_status(self.Status.Searching)
        if self._paused:return
        if not self.timer.isActive():self.timer.start(0)
    def source_match(self,result):
        """Recover exact match spelling and native character bounds.

        Tight kerning can make geometric selection include a preceding hyphen.
        Qt's snippet offsets can also disagree with source character offsets.
        Validate the source range before trusting it for word boundaries.
        """
        parts=[];spans=[];offset=0
        for rect in result.rectangles():
            part=self._document.getSelection(result.page(),QPointF(rect.left(),rect.center().y()),QPointF(rect.right(),rect.center().y()))
            text=part.text()
            parts.append(text);spans.append((offset,offset+len(text),part))
            offset+=len(text)+1
        pattern=r'\s+'.join(re.escape(word) for word in self.searchString().split())
        if not pattern:return None
        match=re.search(pattern,' '.join(parts),re.IGNORECASE)
        if match is None:return None
        first=next((part.startIndex()+match.start()-start for start,end,part in spans if start<=match.start()<end),None)
        last=next((part.startIndex()+match.end()-start for start,end,part in spans if start<match.end()<=end),None)
        spelling=' '.join(match.group().split())
        if first is not None and last is not None:
            selected=self._document.getSelectionAtIndex(result.page(),first,max(0,last-first)).text()
            if ' '.join(selected.split())!=spelling:first=last=None
        return spelling,first,last

    def accepts(self,result):
        query=self.searchString()
        if not self.whole_words and not self.match_case:return True
        source=self.source_match(result)
        before,after=result.contextBefore(),result.contextAfter()
        if source is not None and source[1] is not None:
            _,first,last=source
            before=self._document.getSelectionAtIndex(result.page(),first-1,1).text() if first else ''
            after=self._document.getSelectionAtIndex(result.page(),last,1).text()
        if self.whole_words:
            if word_character(query[:1]) and word_character(before[-1:]):return False
            if word_character(query[-1:]) and word_character(after[:1]):return False
        if self.match_case:
            # Qt can split a match over lines. Normalize whitespace only; case,
            # accents, scientific symbols and punctuation remain significant.
            if source is None or source[0]!=' '.join(query.split()):return False
        return True
    def pump(self):
        if self._paused or not self._document or not self.searchString():return
        total=self.native.rowCount(QModelIndex())
        batch=[];started=time.monotonic();processed=0
        while self._cursor<total and processed<64 and time.monotonic()-started<.005:
            row=self._cursor;self._cursor+=1;processed+=1
            if self.accepts(self.native.resultAtIndex(row)):batch.append(row)
        if batch:
            start=len(self._rows)
            self.beginInsertRows(QModelIndex(),start,start+len(batch)-1)
            self._rows.extend(batch)
            self.endInsertRows()
        if self._cursor<total:self.timer.start(0)
        elif not self._waiting_native and self.native.status()!=self.Status.Searching:self.set_status(self.Status.Finished)
