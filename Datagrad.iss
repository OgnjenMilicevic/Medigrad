; Datagrad.iss — Inno Setup script
; Wraps the PyInstaller one-folder output (dist\Datagrad\) into a single
; installer executable with a Start-menu shortcut, optional desktop icon,
; and a proper uninstaller.
;
; Build: open this file in Inno Setup Compiler (https://jrsoftware.org/isinfo.php)
; and click Compile, or run:  ISCC.exe Datagrad.iss
; Output: Output\Datagrad-Setup.exe

#define MyAppName "Datagrad MFUB Desktop"
#define MyAppVersion "1.0"
#define MyAppPublisher "Medicinski fakultet Univerziteta u Beogradu"
#define MyAppExeName "Datagrad.exe"

[Setup]
AppId={{D47A6B10-3C2E-4F8A-9B1D-DATAGRAD0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=Datagrad-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Per-user install needs no admin rights; switch to "admin" for all-users.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Bundle everything PyInstaller produced in the one-folder build.
Source: "dist\Datagrad\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
