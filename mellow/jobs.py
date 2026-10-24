"""Run PDF file work outside the GUI thread with cooperative cancellation."""
from threading import Event
import time
from PySide6.QtCore import QThread, Signal
from .utilities import Cancelled


class FileJob(QThread):
    progress = Signal(int,int)
    stageChanged = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    def __init__(self,operation,output,parent=None):
        super().__init__(parent)
        self.operation=operation
        self.output=output
        self.cancel_event=Event()
    def cancel(self):
        self.cancel_event.set()
    def run(self):
        try:
            job=self
            class Reporter:
                last=0.0
                def __call__(self,done,total):
                    now=time.monotonic()
                    if done not in (1,total) and now-self.last<.04:return
                    self.last=now
                    if total>2_000_000_000:done,total=round(done/total*10000),10000
                    job.progress.emit(done,total)
                def stage(self,text):self.last=0.0;job.stageChanged.emit(text)
            self.operation(self.cancel_event,Reporter())
        except Cancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit(str(self.output))
