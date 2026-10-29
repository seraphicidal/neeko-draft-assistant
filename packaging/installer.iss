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
ChangesAssociations=yes

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
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "seraphicidal.neekodraftassistant.1.0"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon; AppUserModelID: "seraphicidal.neekodraftassistant.1.0"
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startup; AppUserModelID: "seraphicidal.neekodraftassistant.1.0"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent; Check: not IsSilent
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: IsSilent

[Code]
function IsSilent: Boolean;
begin
  Result := WizardSilent;
end;

procedure CleanNotifyIconCache;
var
  Names: TArrayOfString;
  I: Integer;
  ExePath: String;
begin
  if RegGetSubkeyNames(HKCU, 'Control Panel\NotifyIconSettings', Names) then
  begin
    for I := 0 to GetArrayLength(Names) - 1 do
    begin
      if RegQueryStringValue(HKCU, 'Control Panel\NotifyIconSettings\' + Names[I], 'ExecutablePath', ExePath) then
      begin
        if Pos('neekodraftassistant', Lowercase(ExePath)) > 0 then
          RegDeleteKeyIncludingSubkeys(HKCU, 'Control Panel\NotifyIconSettings\' + Names[I]);
      end;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    CleanNotifyIconCache;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\NeekoDraftAssistant\champions"
