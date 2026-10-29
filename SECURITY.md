# Security

## Reporting a vulnerability

Use [GitHub's private vulnerability reporting](https://github.com/Samiul-Haque-vcode/Mellow_PDF-Reader/security/advisories/new) if enabled. If it is unavailable, open an issue requesting a private reporting channel without posting exploit details, private PDFs, backups or credentials. Include the app version and a description of the impact.

## Reading untrusted files

Mellow operates offline, but PDF parsing uses native Qt/PDFium code. Neither offline operation nor automated tests guarantee that a document is safe. Keep Mellow, its dependencies and Windows updated.

External PDF links are restricted to HTTP/HTTPS and ordinary email links. Local files and custom protocol handlers are blocked. Opening an allowed link launches an external application and can use the network. The app does not upload PDFs for scanning or reference matching.

Metadata imports are size-limited and validated before replacing saved data. Exports use atomic JSON writes and guard against overwriting PDFs or the live database. Backups and Favorites exports can contain document paths, titles and reading history: keep them private. They do not contain the original PDFs.

## Windows downloads and signing

No trusted signing certificate is configured for this project. Version-resource publisher text is descriptive metadata, not an Authenticode signature. Unsigned builds can show SmartScreen reputation warnings. A named antivirus detection is a separate issue: keep the file blocked, record the threat name and SHA-256, and report it. Do not disable protection or add exclusions to install Mellow.

Windows builds create `dist/build-verification/BUILD.json`, `SHA256SUMS.txt` and `SECURITY.json`. They identify the source commit, exact build packages, file hashes, signature status and available Defender results. A missing or unavailable scan is reported as `NotRun`, never as a passed scan. Detections, scan errors and changed build files block publication. A passed scan is point-in-time evidence, not a safety guarantee.

```powershell
Get-FileHash .\MellowPDFReader-Setup.exe -Algorithm SHA256
Get-AuthenticodeSignature .\MellowPDFReader-Setup.exe
```

Compare hashes only with the report for the same build. 1.0.0 is a source release; it has no published installer or binary scan report.

## Building with a signing identity

Install Windows SDK Signing Tools and use an existing code-signing certificate in the current user's Personal (My) store, with its private key and trusted chain:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows.ps1 -CertificateThumbprint YOUR_40_HEX_CERTIFICATE_THUMBPRINT
```

The script signs the executable before building the installer, signs the installer, timestamps via HTTPS and verifies both signatures. Signing failure stops the build. It does not create, export or upload certificates. Signed builds require a successful Defender scan. Without a thumbprint, builds are explicitly unsigned.

For separate verification, use `python packaging/verify_windows.py --require-signed --require-defender`. Signing and antivirus checks do not complete the dependency-attribution or physical-device checks described in [THIRD_PARTY.md](THIRD_PARTY.md) and [Windows validation](docs/windows-validation.md).

## Review scope

[VALIDATION.md](VALIDATION.md) records test and review evidence. Dependency advisory checks cover the named Python distributions, not every native library embedded in Qt/PDFium. Static-analysis warnings are reviewed rather than treated as proof of exploitable bugs or concealed as a clean scan. No claim of comprehensive security certification is made.
