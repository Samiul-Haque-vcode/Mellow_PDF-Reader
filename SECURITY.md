# Windows download warnings

Development builds of Mellow are currently **unsigned**. No trusted publisher certificate or signing service is configured. The executable's product/version information is descriptive metadata; it is not a digital signature.

A SmartScreen message such as **“Windows protected your PC” / “unrecognized app”** concerns download/publisher reputation. New unsigned versions can show it. Proper Authenticode signing with a validated publisher identity helps establish publisher trust, but even a newly signed build can initially show reputation warnings. See [Microsoft's SmartScreen explanation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

A **named antivirus detection**, such as `Trojan:Win32/...`, is different. Record its full threat name, affected path, app version and the file's SHA-256 from Windows Security → Protection history. Keep a flagged file blocked while the detection is investigated. Do not turn off protection or add exclusions to install Mellow. A developer can submit a suspected false positive through [Microsoft Security Intelligence](https://www.microsoft.com/en-us/wdsi/filesubmission); Mellow does not upload files automatically.

## Evidence included with each new Windows build

The **Windows-build-verification** Actions artifact contains:

- `SHA256SUMS.txt`: fingerprints of the installer and every file in the application folder.
- `BUILD.json`: file sizes/hashes, source commit, Python version and exact installed build-package versions.
- `SECURITY.json`: observed Authenticode signatures, Defender engine/signature information, scan result and any changed/missing files.
- Raw `defender-app.log` and `defender-installer.log` when scanning is available.

Defender checks use a custom scan without remediation; this inspects archives and ignores file exclusions, without changing protection settings. Nonzero scan results or changed/missing build files fail the workflow before app downloads are published. If Defender is unavailable or disabled on the runner, the report explicitly says **NotRun**; this is not a passed scan. See [Microsoft's scanner documentation](https://learn.microsoft.com/en-us/defender-endpoint/command-line-arguments-microsoft-defender-antivirus).

To identify your installer in PowerShell:

```powershell
Get-FileHash .\MellowPDFReader-Setup.exe -Algorithm SHA256
Get-AuthenticodeSignature .\MellowPDFReader-Setup.exe
```

Compare the hash with the matching Actions run's report. Hashes identify bytes; they do not prove safety or replace a trusted signature. A **NoThreatsReported** result describes that scanner and definition version at that time. It does not guarantee every antivirus will agree, eliminate SmartScreen prompts, or establish that a prior build was safe.

The build explicitly disables optional UPX compression and includes a Windows version resource. These make packaging choices and identity clearer; they are not antivirus bypasses or a promise to remove warnings. The source and build scripts can be reviewed in this repository. A source review and application tests do not replace a malware scan.

## Building with your signing identity

The 0.13 build script can sign with an existing code-signing certificate in the
current Windows user's **Personal (My)** certificate store. Install Windows SDK
Signing Tools, Python 3.12 x64 and Inno Setup 6 first. The certificate must have
an accessible private key and a trusted code-signing chain. Mellow does not
create a publisher identity, generate a self-signed substitute, export a private
key or upload a certificate. No signing identity is configured on GitHub CI.

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows.ps1 -CertificateThumbprint YOUR_40_HEX_CERTIFICATE_THUMBPRINT
```

The script signs the app **before** compiling the installer, then signs the
installer. Both use SHA-256 and an HTTPS RFC 3161 timestamp. It verifies each
signature with `signtool verify /pa /all`, then fingerprints the final bytes and
requires valid app/installer Authenticode signatures and a real successful
Defender scan. Signing/timestamp failures stop the build; there is no silent
unsigned fallback. The default timestamp endpoint is
`https://timestamp.digicert.com`; `-TimestampUrl` selects another HTTPS service.
Timestamping requires network access only while building, never while reading.

Without `-CertificateThumbprint`, the script produces an explicitly unsigned
development build. GitHub CI currently uses that path. For an independently
built release, enforce the final evidence explicitly:

```powershell
python packaging/verify_windows.py --require-signed --require-defender
```

These options reject unavailable scans or missing/invalid signatures. They do
not complete dependency attribution or physical Windows validation; see
[distribution notes](THIRD_PARTY.md) and [Windows validation](docs/windows-validation.md).
