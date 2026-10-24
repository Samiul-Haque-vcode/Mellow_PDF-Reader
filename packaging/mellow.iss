; Build with Inno Setup 6 after packaging/windows.ps1.
[Setup]
AppId=MellowPDFReader
AppName=Mellow PDF Reader
AppPublisher=Mellow PDF Reader project
AppCopyright=Copyright (c) 2026 Mellow PDF Reader contributors
AppVersion=0.0.3
ChangesAssociations=yes
SetupIconFile=..\mellow\assets\mellow.ico
UninstallDisplayIcon={app}\MellowPDFReader.exe
DefaultDirName={autopf}\Mellow PDF Reader
DefaultGroupName=Mellow PDF Reader
OutputDir=..\dist
OutputBaseFilename=MellowPDFReader-Setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
[Files]
Source: "..\dist\MellowPDFReader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Mellow PDF Reader"; Filename: "{app}\MellowPDFReader.exe"; AppUserModelID: "Mellow.PDFReader"
[Messages]
ConfirmUninstall=Uninstall %1 and remove this Windows user's saved sessions, settings, Favorites and bookmarks? Your PDF files and exported backups will be kept.
[UninstallDelete]
; Exact app-owned files only: never recursively delete a folder that may
; contain a user's PDFs, exported backups, or other documents.
Type: files; Name: "{localappdata}\Mellow\Mellow PDF Reader\mellow.sqlite3"
Type: files; Name: "{localappdata}\Mellow\Mellow PDF Reader\mellow.sqlite3-journal"
Type: files; Name: "{localappdata}\Mellow\Mellow PDF Reader\mellow.sqlite3-wal"
Type: files; Name: "{localappdata}\Mellow\Mellow PDF Reader\mellow.sqlite3-shm"
Type: dirifempty; Name: "{localappdata}\Mellow\Mellow PDF Reader"
Type: dirifempty; Name: "{localappdata}\Mellow"
[Registry]
; Offer Open with Mellow; leave the user's chosen default PDF application alone.
Root: HKA; Subkey: "Software\Classes\MellowPDFReader.PDF"; ValueType: string; ValueData: "PDF document"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\MellowPDFReader.PDF\DefaultIcon"; ValueType: string; ValueData: """{app}\MellowPDFReader.exe"",0"
Root: HKA; Subkey: "Software\Classes\MellowPDFReader.PDF\shell\open\command"; ValueType: string; ValueData: """{app}\MellowPDFReader.exe"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "MellowPDFReader.PDF"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\MellowPDFReader.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "Mellow PDF Reader"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\MellowPDFReader.exe\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\MellowPDFReader.exe\shell\open\command"; ValueType: string; ValueData: """{app}\MellowPDFReader.exe"" ""%1"""
[Run]
Filename: "{app}\MellowPDFReader.exe"; Description: "Open Mellow PDF Reader"; Flags: nowait postinstall skipifsilent
