#define AppVersion "0.9.0"
#ifndef PayloadRoot
  #define PayloadRoot "..\package\payload"
#endif
[Setup]
AppId={{517B810E-4D4E-4C37-93AB-4D7C405E4779}
AppName=Triceratops Music Agent for REAPER
AppVersion={#AppVersion}
AppPublisher=Aolin-MIR
AppPublisherURL=https://github.com/Aolin-MIR/triceratops-music-agent
AppSupportURL=https://github.com/Aolin-MIR/triceratops-music-agent/issues
DefaultDirName={autopf}\Triceratops
DefaultGroupName=Triceratops
OutputDir=..\package\release
OutputBaseFilename=Triceratops-0.9.0-Windows-x64-Setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
MinVersion=10.0
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayName=Triceratops Music Agent 0.9
SetupLogging=yes
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
[Files]
Source: "{#PayloadRoot}\Triceratops.vst3\*"; DestDir: "{commoncf64}\VST3\Triceratops.vst3"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Setup-Runtime.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements-runtime.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\package\tools\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
[Icons]
Name: "{group}\Configure runtime and download models"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\Setup-Runtime.ps1"""; WorkingDir: "{app}"
Name: "{group}\Readme (English)"; Filename: "{app}\docs\README.en.md"
Name: "{group}\Readme (Chinese)"; Filename: "{app}\docs\readme.md"
Name: "{group}\Uninstall Triceratops"; Filename: "{uninstallexe}"
[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft C++ runtime..."; Flags: waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\Setup-Runtime.ps1"""; Description: "Configure native runtime and download models (Internet required)"; Flags: postinstall skipifsilent runasoriginaluser
[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if CheckForMutexes('REAPER') then
    Result := 'Please save your REAPER project and close REAPER before updating Triceratops.';
end;
