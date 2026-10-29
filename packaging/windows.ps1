param(
    [string]$CertificateThumbprint = "",
    [string]$TimestampUrl = "https://timestamp.digicert.com",
    [switch]$DistributionReady
)
$ErrorActionPreference = "Stop"
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Python setup failed" }
$Python = ".\.venv\Scripts\python.exe"
& $Python -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
& $Python -m PyInstaller --noconfirm --clean --noupx --windowed --onedir --version-file packaging/version_info.txt --name MellowPDFReader --icon mellow/assets/mellow.ico --add-data "mellow/assets:mellow/assets" --collect-all PySide6.QtPdf --collect-all PySide6.QtPdfWidgets run_mellow.py
if ($LASTEXITCODE -ne 0) { throw "Packaging failed" }
$NoticeArguments = @("packaging/collect_notices.py", "dist/MellowPDFReader")
if ($DistributionReady) { $NoticeArguments += "--require-complete" }
& $Python @NoticeArguments
if ($LASTEXITCODE -ne 0) { throw "Notice collection failed" }
if ($CertificateThumbprint) {
    & $Python packaging/sign_windows.py --thumbprint $CertificateThumbprint --timestamp $TimestampUrl dist/MellowPDFReader/MellowPDFReader.exe
    if ($LASTEXITCODE -ne 0) { throw "Application signing failed" }
}
& $Python packaging/smoke_test.py dist/MellowPDFReader/MellowPDFReader.exe
if ($LASTEXITCODE -ne 0) { throw "Packaged renderer failed" }

$Compiler = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6/ISCC.exe"
if (!(Test-Path $Compiler)) { throw "Install Inno Setup 6 to compile packaging/mellow.iss." }
& $Compiler packaging/mellow.iss
if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed" }
$VerificationArgs = @("packaging/verify_windows.py")
if ($DistributionReady) { $VerificationArgs += "--require-defender" }
if ($CertificateThumbprint) {
    & $Python packaging/sign_windows.py --thumbprint $CertificateThumbprint --timestamp $TimestampUrl dist/MellowPDFReader-Setup.exe
    if ($LASTEXITCODE -ne 0) { throw "Installer signing failed" }
    $VerificationArgs += @("--require-signed", "--require-defender")
}
& $Python @VerificationArgs
if ($LASTEXITCODE -ne 0) { throw "Build verification failed" }
Write-Host "Built and verified dist/MellowPDFReader-Setup.exe"
