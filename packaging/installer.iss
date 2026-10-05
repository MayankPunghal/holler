; Inno Setup script for the Windows installer.  Build (after PyInstaller):
;   iscc /DAppVersion=1.2.0 packaging\installer.iss      ->  dist\Holler-Setup-1.2.0.exe
; Installs for the current user only (no admin prompt) into %LOCALAPPDATA%\Programs\Holler.
; Your settings, vocabulary and models live in %APPDATA%\Holler and survive updates and uninstalls (you're asked).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Holler"
#define AppPublisher "Mayank Punghal"
#define AppURL "https://github.com/MayankPunghal/holler"
#define Brand "..\build\brand"

[Setup]
AppId={{5BA35A6F-D32C-425F-AB92-F89B266C1947}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
AppCopyright=Copyright (c) {#AppPublisher}. MIT licence.
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} installer
VersionInfoProductName={#AppName}
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
UsePreviousTasks=yes
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=Holler-Setup-{#AppVersion}
SetupIconFile={#Brand}\holler.ico
UninstallDisplayIcon={app}\Holler.exe
UninstallDisplayName={#AppName}
WizardStyle=modern
WizardImageFile={#Brand}\wizard-large-1x.bmp,{#Brand}\wizard-large-2x.bmp
WizardSmallImageFile={#Brand}\wizard-small-1x.bmp,{#Brand}\wizard-small-2x.bmp
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
ShowLanguageDialog=no
CloseApplications=no

[Messages]
WelcomeLabel2=This installs [name/ver] on your computer.%n%nHold a key, speak, and your words appear in any app. Speech recognition runs entirely on this computer: no account, no cloud, free.%n%nAfter installing, Holler asks which speech model to download (a one-time download).
FinishedLabel=Holler is installed. Hold Ctrl+Shift, speak, and let go to dictate.%n%nLook for its icon in the system tray (near the clock); right-click it for Settings.

[Tasks]
Name: "autostart"; Description: "Start Holler when I sign in to Windows"; GroupDescription: "Options:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Options:"; Flags: unchecked

[Files]
Source: "..\dist\Holler\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; a clean _internal folder on every update, so files from an older version never linger
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\Holler.exe"; Comment: "Offline push-to-talk dictation"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Holler.exe"; Tasks: desktopicon

[Registry]
; the same entry Holler's own "Start with the computer" switch writes, so the two always agree
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; \
  ValueData: """{app}\Holler.exe"" supervise"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Holler.exe"; Description: "Start Holler now"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\holler-cli.exe"; Parameters: "stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopHoller"

[Code]
procedure StopHoller(Dir: String);
var
  Code: Integer;
begin
  { ask a running Holler (from this app or a pip install: they share one data folder) to stop }
  if FileExists(Dir + '\holler-cli.exe') then
    Exec(Dir + '\holler-cli.exe', 'stop', '', SW_HIDE, ewWaitUntilTerminated, Code);
  { and make sure nothing still holds files in the install folder }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM Holler.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM holler-cli.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopHoller(WizardDirValue);
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and not WizardIsTaskSelected('autostart') then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', '{#AppName}');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Data: String;
begin
  if CurUninstallStep = usUninstall then
    StopHoller(ExpandConstant('{app}'));
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
  begin
    Data := ExpandConstant('{userappdata}\Holler');
    if DirExists(Data) and (MsgBox('Also delete your Holler settings, vocabulary, history and downloaded speech models?' + #13#10#13#10 +
        'Choose No to keep them for a later reinstall (they are in ' + Data + ').',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
      DelTree(Data, True, True, True);
  end;
end;
