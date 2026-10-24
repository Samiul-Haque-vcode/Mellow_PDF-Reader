"""Atomic, cancellable PDF utilities. Never write to a source document."""
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from pypdf import PdfReader, PdfWriter


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled('Operation cancelled')


def page_range(text,count):
    pages=[]
    for part in text.split(','):
        bits=part.strip().split('-')
        if len(bits) not in (1,2):
            raise ValueError('Use ranges such as 1-5,8,12-14')
        a,b=int(bits[0]),int(bits[-1])
        if not 1<=a<=b<=count:
            raise ValueError(f'Pages must be between 1 and {count}')
        pages.extend(range(a-1,b))
    return pages


def safe_output(output,sources):
    destination=Path(output).resolve()
    for source in sources:
        path=Path(source).resolve()
        if destination==path or (destination.exists() and path.exists() and os.path.samefile(destination,path)):
            raise ValueError('Choose a new output file to preserve the original documents.')


def atomic_output(output,write,cancel=None):
    """A failed/cancelled conversion leaves the previous destination intact."""
    output=Path(output)
    fd,temp=tempfile.mkstemp(prefix='.mellow-',suffix='.pdf',dir=output.resolve().parent)
    os.close(fd)
    try:
        write(temp)
        check_cancel(cancel)
        os.replace(temp,output)
    finally:
        if os.path.exists(temp): os.unlink(temp)


class CancelIO:
    """Check cancellation at parser reads and serializer writes, not just pages."""
    def __init__(self,stream,cancel):self.stream,self.cancel=stream,cancel
    def __getattr__(self,name):return getattr(self.stream,name)
    def read(self,*args):check_cancel(self.cancel);return self.stream.read(*args)
    def write(self,data):check_cancel(self.cancel);return self.stream.write(data)
    def seek(self,*args):check_cancel(self.cancel);return self.stream.seek(*args)


def stage(progress,text):
    if progress and hasattr(progress,'stage'):progress.stage(text)


@contextmanager
def source_pdf(path,cancel):
    check_cancel(cancel)
    with open(path,'rb') as stream:
        reader=PdfReader(CancelIO(stream,cancel))
        try:yield reader
        finally:reader.close()


def write_pdf(writer,path,cancel):
    with open(path,'wb') as stream:writer.write(CancelIO(stream,cancel))


def extract(source,output,ranges,cancel=None,progress=None):
    safe_output(output,[source]);stage(progress,'Reading source PDF…')
    writer=PdfWriter()
    try:
        with source_pdf(source,cancel) as reader:
            pages=page_range(ranges,len(reader.pages))
            stage(progress,'Extracting pages…')
            for i,page in enumerate(pages):
                check_cancel(cancel);writer.add_page(reader.pages[page])
                if progress:progress(i+1,len(pages)+1)
            stage(progress,'Writing output PDF…')
            atomic_output(output,lambda path:write_pdf(writer,path,cancel),cancel)
            if progress:progress(len(pages)+1,len(pages)+1)
    finally:writer.close()


def merge(sources,output,cancel=None,progress=None):
    class MergeWriter(PdfWriter):
        def add_page(self,page,*args,**kwargs):
            check_cancel(cancel)
            result=super().add_page(page,*args,**kwargs)
            self.done+=1
            if progress:progress(self.done,self.total+1)
            return result
    safe_output(output,sources);writer=MergeWriter();writer.done=0;writer.total=1
    try:
        # Parse each source only when reached. Progress includes both files and
        # pages without holding every source document open at once.
        for i,path in enumerate(sources):
            stage(progress,f'Reading PDF {i+1} of {len(sources)}…')
            with source_pdf(path,cancel) as reader:
                count=len(reader.pages)
                stage(progress,f'Merging PDF {i+1} of {len(sources)} · {count} pages…')
                writer.done=0;writer.total=count
                writer.append(reader)
        stage(progress,'Writing merged PDF…')
        atomic_output(output,lambda path:write_pdf(writer,path,cancel),cancel)
        if progress:progress(1,1)
    finally:writer.close()


def arrange(source,output,entries,cancel=None,progress=None):
    """Reorder every page once and add clockwise rotations, keeping destinations.

    append() remaps internal links, named destinations and outlines to the new
    page objects. Rotations use /Rotate, retaining original content coordinates.
    """
    class ArrangeWriter(PdfWriter):
        def add_page(self,page,*args,**kwargs):
            check_cancel(cancel)
            result=super().add_page(page,*args,**kwargs)
            if progress:progress(len(self.pages),self.total+1)
            return result
    safe_output(output,[source])
    writer=ArrangeWriter()
    try:
        stage(progress,'Reading pages…')
        with source_pdf(source,cancel) as reader:
            count=len(reader.pages)
            if len(entries)!=count or any(not isinstance(entry,(tuple,list)) or len(entry)!=2 for entry in entries):
                raise ValueError('The page arrangement must contain every output page once.')
            order=[entry[0] for entry in entries]
            angles=[entry[1] for entry in entries]
            if any(type(page) is not int for page in order) or sorted(order)!=list(range(count)):
                raise ValueError('The page arrangement must contain every output page once.')
            if any(type(angle) is not int or angle not in (0,90,180,270) for angle in angles):
                raise ValueError('Page rotations must be 0, 90, 180 or 270 degrees.')
            writer.total=count
            stage(progress,'Arranging pages…')
            writer.append(reader,pages=order)
            labels=reader.page_labels if '/PageLabels' in reader.root_object else None
            for index,(page,angle) in enumerate(entries):
                check_cancel(cancel)
                writer.pages[index].rotation=(writer.pages[index].rotation+angle)%360
                if labels:writer.set_page_label(index,index,prefix=labels[page])
            stage(progress,'Writing arranged PDF…')
            atomic_output(output,lambda path:write_pdf(writer,path,cancel),cancel)
            if progress:progress(count+1,count+1)
    finally:writer.close()


def copy_output(source,destination,cancel=None,progress=None):
    size=Path(source).stat().st_size
    stage(progress,'Saving PDF…')
    def copy(path):
        done=0
        with open(source,'rb') as original,open(path,'wb') as target:
            while True:
                check_cancel(cancel);chunk=original.read(1024*1024)
                if not chunk:break
                target.write(chunk);done+=len(chunk)
                if progress:progress(done,max(1,size))
    atomic_output(destination,copy,cancel)


def images_to_pdf(sources,output,page_size='A4',cancel=None,progress=None):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPdfWriter, QPageSize, QPainter
    safe_output(output,sources)
    stage(progress,'Converting images…')
    def write(path):
        writer=QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4 if page_size=='A4' else QPageSize.PageSizeId.Letter))
        writer.setResolution(144)
        painter=QPainter(writer)
        if not painter.isActive(): raise ValueError('Cannot write PDF')
        try:
            for i,source in enumerate(sources):
                check_cancel(cancel)
                image=QImage(str(source))
                if image.isNull(): raise ValueError(f'Cannot read image: {source}')
                if i: writer.newPage()
                scaled=image.scaled(writer.width(),writer.height(),Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
                painter.drawImage((writer.width()-scaled.width())//2,(writer.height()-scaled.height())//2,scaled)
                if progress: progress(i+1,len(sources))
        finally:
            stage(progress,'Finishing output PDF…')
            painter.end()
            del writer  # Flush the file before atomic_output renames it on Windows.
    atomic_output(output,write,cancel)
