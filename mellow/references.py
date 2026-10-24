"""Offline, incremental reference matching. No OCR or external service."""
import re
from dataclasses import dataclass
from PySide6.QtCore import QObject, QTimer, Signal, QPointF

LABEL = r'(?P<number>\d+(?:[.\-]\d+)*[a-z]?)'
REFERENCE = re.compile(r'\b(?P<kind>fig(?:ure)?s?\.?|eq(?:uation)?s?\.?|tables?|sections?|sec\.?)\s*\(?'+LABEL+r'\)?', re.I)
ALIASES = {'fig': 'Figure', 'figure': 'Figure', 'eq': 'Equation', 'equation': 'Equation',
           'table': 'Table', 'section': 'Section', 'sec': 'Section'}


def references_in(text):
    found = []
    for match in REFERENCE.finditer(text):
        kind = ALIASES.get(match['kind'].lower().rstrip('.').rstrip('s'))
        label = f'{kind} {match["number"]}'
        if label not in found:
            found.append(label)
    return found


@dataclass
class Target:
    page: int
    x: float = 0
    y: float = 0
    title: str = 'Reference preview'
    evidence: str = ''
    excerpt: str = ''
    def point(self):
        return QPointF(self.x, self.y)


class ReferenceResolver(QObject):
    progress = Signal(int, int)
    finished = Signal(object)
    def __init__(self, document, label, source_page, parent=None):
        super().__init__(parent)
        self.document = document
        self.source_page = source_page
        self.label = label
        self.pages = iter(range(document.pageCount()))
        self.candidates = []
        self._cancelled = False
        self.timer = QTimer(self)
        self.timer.setInterval(1)
        self.timer.timeout.connect(self.tick)
        match = REFERENCE.search(label)
        if not match:
            raise ValueError('Use a reference such as Figure 3.8 or Equation (2.4).')
        self.kind = ALIASES[match['kind'].lower().rstrip('.').rstrip('s')]
        self.number = match['number']
        self.number_pattern = re.compile(r'(?<![\w.])\('+re.escape(self.number)+r'\)(?![\w.])', re.I)
        self.count = 0
    def start(self):
        if self._cancelled:return
        self.timer.start()
    def cancel(self):
        self._cancelled=True
        self.timer.stop()
    def tick(self):
        if self._cancelled:return
        try:
            page = next(self.pages)
        except StopIteration:
            self.timer.stop()
            # A caption is stronger evidence than a prose citation. Present ties
            # for the reader to choose; do not silently claim certainty.
            ranked = sorted(self.candidates, key=lambda c: (-c[0], abs(c[1].page-self.source_page)))
            self.finished.emit([target for _, target in ranked[:30]])
            return
        text = self.document.getAllText(page).text()
        offsets = []
        for match in REFERENCE.finditer(text):
            kind = ALIASES.get(match['kind'].lower().rstrip('.').rstrip('s'))
            if kind == self.kind and match['number'].casefold() == self.number.casefold():
                prefix = text[text.rfind('\n', 0, match.start())+1:match.start()]
                rest=text[match.end():].split('\n',1)[0].strip()
                citation=re.match(r'(?:shows?|illustrates?|describes?|presents?|compares?|is|are|was|were|contains?|depicts?|summari[sz]es?|can|could|should|will|would|has|have|had)\b',rest,re.I)
                score = 4 if not prefix.strip() and not citation else 1
                offsets.append((match.start(), match.end()-match.start(), score,
                                'Caption-like text' if score==4 else 'Text citation'))
        if self.kind == 'Equation':
            for match in self.number_pattern.finditer(text):
                if any(start<=match.start()<start+length for start,length,_,_ in offsets):continue
                line = text[text.rfind('\n',0,match.start())+1:match.start()]
                suffix=text[match.end():].split('\n',1)[0].strip()
                math_line=not line.strip() or any(char in line for char in '=+−∑∫√≈≤≥×÷≠≡±∂∞∏∇()[]_^')
                score=3 if not suffix and math_line and not REFERENCE.search(line) else 1
                offsets.append((match.start(), match.end()-match.start(), score,
                                'Possible equation label' if score==3 else 'Text citation'))
        if self.kind == 'Section':
            heading = re.compile(r'^[^\S\r\n]*'+re.escape(self.number)+r'[^\S\r\n]+\S[^\r\n]*', re.M)
            for match in heading.finditer(text):
                contents=bool(re.search(r'(?:\.[ ]*){3,}.*\b(?:\d+|[ivxlcdm]+)\s*$',match.group(),re.I))
                offsets.append((match.start(),match.end()-match.start(),2 if contents else 5,
                                'Contents entry' if contents else 'Possible section heading'))
        for start, length, score, evidence in offsets:
            selection = self.document.getSelectionAtIndex(page,start,length)
            # Broken glyph/character mappings must not produce a false target
            # at the page origin. Retain the manual-preview fallback instead.
            if not selection.isValid() or selection.text()!=text[start:start+length]:continue
            bounds = selection.boundingRectangle()
            if bounds.isEmpty():continue
            line_start=text.rfind('\n',0,start)+1
            line_end=text.find('\n',start+length)
            if line_end<0:line_end=len(text)
            excerpt=' '.join(text[line_start:line_end].split())
            if len(excerpt)>140:excerpt=excerpt[:137]+'…'
            target = Target(page, max(0,bounds.x()-12), max(0,bounds.y()-48), f'{self.label} · page {page+1}',evidence,excerpt)
            self.candidates.append((score,target))
        # Retain only the best choices while scanning, not every citation in a
        # long book. Page-distance is a tie-breaker, never a certainty claim.
        self.candidates.sort(key=lambda c:(-c[0],abs(c[1].page-self.source_page),c[1].page,c[1].y))
        del self.candidates[30:]
        self.count += 1
        self.progress.emit(self.count,self.document.pageCount())
