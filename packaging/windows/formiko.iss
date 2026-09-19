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

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Formiko"; Flags: nowait postinstall skipifsilent
