"""Run the frozen app, not the source tree, and require successful PDF rendering."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from reportlab.pdfgen.canvas import Canvas

def main():
    with tempfile.TemporaryDirectory(prefix='mellow-package-') as directory:
        path=Path(directory)/'sample.pdf'
        canvas=Canvas(str(path))
        canvas.drawString(40,700,'Mellow packaged rendering smoke test')
        canvas.showPage()
        canvas.save()
        env=os.environ.copy()
        env['QT_QPA_PLATFORM']='offscreen'
        subprocess.run([str(Path(sys.argv[1]).resolve()),'--smoke-test',str(path)],
                       check=True,timeout=45,env=env)
    print('Packaged reader and PDF-tool preview smoke tests passed.')

if __name__=='__main__': main()
