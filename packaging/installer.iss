; Inno Setup script for Neeko's Little Draft Assistant.
;
; The version and paths are passed in by tools/build.py so that core/version.py
; stays the only place a version number is written down:
;
;   ISCC /DAppVersion=1.0.0 /DSourceDir=..\dist\NeekoDraftAssistant packaging\installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\NeekoDraftAssistant"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

#define AppName "Neeko's Little Draft Assistant"
#define AppShortName "NeekoDraftAssistant"
#define AppExe "NeekoDraftAssistant.exe"
#define AppPublisher "Chris"
#define AppUrl "https://github.com/seraphicidal/neeko-draft-assistant"

[Setup]
AppId={{8E2C6F41-3B7A-4C25-9E1D-6A0F4B7C9D31}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
VersionInfoVersion={#AppVersion}

; Installs per-user, so no administrator prompt is needed.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\{#AppShortName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}

OutputDir={#OutputDir}
OutputBaseFilename={#AppShortName}-{#AppVersion}-Setup
SetupIconFile=..\assets\icon.ico
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

; Shut the running copy down before overwriting it, and start it again after.
CloseApplications=yes
CloseApplicationsFilter=*.exe,*.dll
RestartApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startup"; Description: "Start &Neeko when I sign in"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; The cached champion art is ours to clean up. Settings in {userappdata} are
; deliberately left alone -- an uninstall should not throw away her champion.
Type: filesandordirs; Name: "{localappdata}\NeekoDraftAssistant\champions"
