# Exercise the real Inno installer/uninstaller in a disposable Windows account.
# Refuse existing app metadata so this check cannot erase a reader's saved data.
param([string]$SetupPath = "dist/MellowPDFReader-Setup.exe")
$ErrorActionPreference = 'Stop'
$metadata = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Mellow\Mellow PDF Reader'
$database = Join-Path $metadata 'mellow.sqlite3'
$owned = @($database, "$database-journal", "$database-wal", "$database-shm")
$document = Join-Path $metadata 'uninstall-check-document.pdf'
$backup = Join-Path $metadata 'uninstall-check-backup.json'
foreach ($path in ($owned + @($document, $backup))) {
    if (Test-Path -LiteralPath $path) { throw "Uninstall check refuses existing data: $path" }
}
$target = Join-Path ([IO.Path]::GetTempPath()) ('mellow-uninstall-' + [guid]::NewGuid())
$readingBackup = "$target.mellow-backup.json"
$setup = (Resolve-Path -LiteralPath $SetupPath).Path
function Install-Reader {
    $result = Start-Process -FilePath $setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/DIR="' + $target + '"') -Wait -PassThru
    if ($result.ExitCode -ne 0) { throw "Installer failed: $($result.ExitCode)" }
}
function Uninstall-Reader {
    $result = Start-Process -FilePath (Join-Path $target 'unins000.exe') -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait -PassThru
    if ($result.ExitCode -ne 0) { throw "Uninstaller failed: $($result.ExitCode)" }
}
try {
    Install-Reader
    # Resolve the same Qt path and create real app metadata, a PDF and a backup.
    @'
import sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from reportlab.pdfgen.canvas import Canvas
from mellow.config import data_directory
from mellow.storage import Store
from mellow import backup
app=QCoreApplication([])
app.setOrganizationName('Mellow');app.setApplicationName('Mellow PDF Reader')
root=data_directory()
assert root.resolve()==Path(sys.argv[1]).resolve(),(root,sys.argv[1])
store=Store(root/'mellow.sqlite3')
document=root/'uninstall-check-document.pdf'
canvas=Canvas(str(document));canvas.drawString(40,700,'Keep this original PDF');canvas.save()
store.set('session',{'active':0,'paths':[str(document)]})
store.set('theme','Sepia');store.set('shortcuts',{'fullscreen':'F11'})
store.add('favorite',document,0,'Keep favorite until uninstall')
store.add('bookmark',document,0,'Keep bookmark until uninstall')
backup.write(store,sys.argv[2])
store.db.close()
(root/'uninstall-check-backup.json').write_text('{"backup":"keep"}')
'@ | python - $metadata $readingBackup
    if ($LASTEXITCODE -ne 0) { throw 'Metadata fixture failed' }
    $hash = (Get-FileHash -LiteralPath $database).Hash
    $documentHash = (Get-FileHash -LiteralPath $document).Hash
    $backupHash = (Get-FileHash -LiteralPath $backup).Hash
    Install-Reader
    if ((Get-FileHash -LiteralPath $database).Hash -ne $hash) { throw 'Update erased or modified saved data' }
    # Simulate leftover SQLite companion files after closing the application.
    foreach ($path in $owned[1..3]) { Set-Content -LiteralPath $path 'SQLite fixture' }
    Uninstall-Reader
    foreach ($path in $owned) {
        if (Test-Path -LiteralPath $path) { throw "Uninstall kept personal data: $path" }
    }
    if ((Get-FileHash -LiteralPath $document).Hash -ne $documentHash) { throw 'Uninstall changed the PDF' }
    if ((Get-FileHash -LiteralPath $backup).Hash -ne $backupHash) { throw 'Uninstall changed the exported backup' }
    Install-Reader
    if (Test-Path -LiteralPath $database) { throw 'Reinstall restored old personal data' }
    @'
import sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from mellow.config import data_directory
from mellow.storage import Store
from mellow import backup
app=QCoreApplication([])
app.setOrganizationName('Mellow');app.setApplicationName('Mellow PDF Reader')
store=Store(data_directory()/'mellow.sqlite3')
data=backup.read(sys.argv[1]);backup.replace(store,data)
assert backup.snapshot(store)==data
assert store.get('theme')=='Sepia'
assert len(store.locations('favorite'))==1 and len(store.locations('bookmark'))==1
assert Path(store.locations('favorite')[0]['path']).is_file()
store.db.close()
print('Metadata backup restored after actual reinstall; original PDF still present.')
'@ | python - $readingBackup
    if ($LASTEXITCODE -ne 0) { throw 'Backup restore after reinstall failed' }
    Uninstall-Reader
    Write-Host 'Uninstall removed saved data; in-place update preserved it; PDF and exported backup unchanged; reinstall starts clean.'
} finally {
    if (Test-Path (Join-Path $target 'unins000.exe')) { Uninstall-Reader }
    # Only test-owned files; never recursively erase the metadata directory.
    foreach ($path in ($owned + @($document, $backup))) { Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $readingBackup -Force -ErrorAction SilentlyContinue
    try { [IO.Directory]::Delete($metadata) } catch { }
}
