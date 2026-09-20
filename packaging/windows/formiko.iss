; Inno Setup script for the Windows installer.
; Built by .github/workflows/build-windows-installer.yml from the PyInstaller
; output in dist/formiko/. Also needs these generated in the repository root:
; formiko.ico, the wizard-*.png images (make_wizard_images.py) and
; formiko_meta.iss (generate_metadata.py, which reads the name, version,
; author, homepage and copyright from formiko/__init__.py). Run with:
;   iscc packaging\windows\formiko.iss

#include "..\..\formiko_meta.iss"
#define MyAppSupportURL "https://github.com/ondratu/formiko/issues"
#define MyAppUpdatesURL "https://github.com/ondratu/formiko/releases"

[Setup]
AppId={{6E8F6C2B-4E9C-4B5A-9D9A-2C6E9A6F1B34}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppSupportURL}
AppUpdatesURL={#MyAppUpdatesURL}
AppContact={#MyAppContact}
AppComments={#MyAppComments}
AppCopyright={#MyAppCopyright}
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\..\COPYING
VersionInfoVersion={#MyAppNumericVersion}
VersionInfoProductVersion={#MyAppNumericVersion}
VersionInfoProductTextVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoCompany={#MyAppPublisher}
VersionInfoCopyright={#MyAppCopyright}
VersionInfoDescription={#MyAppName} Setup
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\..\dist\installer
OutputBaseFilename=formiko-{#MyAppVersion}-windows-x64-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\..\formiko.ico
WizardImageFile=..\..\wizard-large-202.png,..\..\wizard-large-336.png,..\..\wizard-large-430.png
WizardSmallImageFile=..\..\wizard-small-58.png,..\..\wizard-small-97.png,..\..\wizard-small-124.png
DisableProgramGroupPage=yes
ChangesAssociations=yes
; GTK4 needs Windows 10 or later; x64compatible also covers Windows on ARM.
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\..\dist\formiko\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\COPYING"; DestDir: "{app}"; DestName: "COPYING.txt"; Flags: ignoreversion
; Licences of the bundled MSYS2 libraries (GTK, GLib, Cairo, ...).
Source: "..\..\dist-runtime\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppComments}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppComments}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "associate"; Description: "Open .&rst and .md files with Formiko (only where no other program is set yet)"; GroupDescription: "File associations:"

[Registry]
; Formiko always registers itself as a program that can open .rst, .md and
; .json files: it shows up under "Open with" and in Settings > Default
; apps, but never replaces a program the user already chose. .json gets
; nothing beyond that; .rst and .md may additionally become the default
; when the "associate" task is selected (see [Code]).
Root: HKA; Subkey: "Software\Classes\Formiko.rst"; ValueType: string; ValueName: ""; ValueData: "reStructuredText document"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Formiko.rst\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\Formiko.rst\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.rst\OpenWithProgids"; ValueType: string; ValueName: "Formiko.rst"; ValueData: ""; Flags: uninsdeletevalue

Root: HKA; Subkey: "Software\Classes\Formiko.md"; ValueType: string; ValueName: ""; ValueData: "Markdown document"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Formiko.md\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\Formiko.md\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.md\OpenWithProgids"; ValueType: string; ValueName: "Formiko.md"; ValueData: ""; Flags: uninsdeletevalue

Root: HKA; Subkey: "Software\Classes\Formiko.json"; ValueType: string; ValueName: ""; ValueData: "JSON document"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Formiko.json\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\Formiko.json\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.json\OpenWithProgids"; ValueType: string; ValueName: "Formiko.json"; ValueData: ""; Flags: uninsdeletevalue

Root: HKA; Subkey: "Software\Formiko"; ValueType: none; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Formiko\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Formiko\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "{#MyAppComments}"
Root: HKA; Subkey: "Software\Formiko\Capabilities\FileAssociations"; ValueType: string; ValueName: ".rst"; ValueData: "Formiko.rst"
Root: HKA; Subkey: "Software\Formiko\Capabilities\FileAssociations"; ValueType: string; ValueName: ".md"; ValueData: "Formiko.md"
Root: HKA; Subkey: "Software\Formiko\Capabilities\FileAssociations"; ValueType: string; ValueName: ".json"; ValueData: "Formiko.json"
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: "Software\Formiko\Capabilities"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Formiko"; Flags: nowait postinstall skipifsilent

[Code]
{ Make Formiko the default for Ext, but only if nothing is set yet - in
  HKCR, the merged per-user and per-machine view Windows itself reads. }
procedure SetDefaultIfUnset(Ext: String);
var
  Current: String;
begin
  if not RegQueryStringValue(HKCR, Ext, '', Current) or (Current = '') then
    RegWriteStringValue(HKA, 'Software\Classes\' + Ext, '', 'Formiko' + Ext);
end;

{ Undo SetDefaultIfUnset, leaving a default that another program set alone. }
procedure ClearDefaultIfOurs(Ext: String);
var
  Key, Current: String;
begin
  Key := 'Software\Classes\' + Ext;
  if RegQueryStringValue(HKA, Key, '', Current) and (Current = 'Formiko' + Ext) then
    RegDeleteValue(HKA, Key, '');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('associate') then
  begin
    SetDefaultIfUnset('.rst');
    SetDefaultIfUnset('.md');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    ClearDefaultIfOurs('.rst');
    ClearDefaultIfOurs('.md');
  end;
end;
