; Inno Setup script for the Windows installer.
; Built by .github/workflows/build-windows-installer.yml from the PyInstaller
; output in dist/formiko/, plus formiko.ico and the wizard-*.png images
; (make_wizard_images.py) generated in the repository root. Run with:
;   iscc /DMyAppVersion="<version>" packaging\windows\formiko.iss
; MyAppVersion defaults to 0.0.0 so the script still compiles standalone.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "Formiko"
#define MyAppPublisher "Ondrej Tuma"
#define MyAppURL "https://formiko.zeropage.cz"
#define MyAppExeName "formiko.exe"

[Setup]
AppId={{6E8F6C2B-4E9C-4B5A-9D9A-2C6E9A6F1B34}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\..\dist\installer
OutputBaseFilename=formiko-{#MyAppVersion}-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\..\formiko.ico
WizardImageFile=..\..\wizard-large-202.png,..\..\wizard-large-336.png,..\..\wizard-large-430.png
WizardSmallImageFile=..\..\wizard-small-58.png,..\..\wizard-small-97.png,..\..\wizard-small-124.png
UninstallDisplayIcon={app}\{#MyAppExeName}
; Per-user install: no UAC prompt for setup or for unins000.exe (whose
; name Inno Setup does not let you change).
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\..\dist\formiko\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Formiko"; Flags: nowait postinstall skipifsilent
