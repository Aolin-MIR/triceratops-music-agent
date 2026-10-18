#define AppVersion "1.0.0"
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
OutputBaseFilename=Triceratops-1.0.0-Windows-x64-Setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
MinVersion=10.0
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayName=Triceratops Music Agent 1.0
SetupLogging=yes
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
[Files]
Source: "{#PayloadRoot}\Triceratops.vst3\*"; DestDir: "{commoncf64}\VST3\Triceratops.vst3"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\ollama\*"; DestDir: "{app}\ollama"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\llama-cpp\*"; DestDir: "{app}\llama-cpp"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\package\tools\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
[Icons]
Name: "{group}\Readme (English)"; Filename: "{app}\docs\README.en.md"
Name: "{group}\Readme (Chinese)"; Filename: "{app}\docs\readme.md"
Name: "{group}\Uninstall Triceratops"; Filename: "{uninstallexe}"
[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft C++ runtime..."; Flags: waituntilterminated
Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 ""{app}\backend\text2music\agent\first_run.py"""; StatusMsg: "Preparing in-plugin setup..."; Flags: waituntilterminated runasoriginaluser

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if CheckForMutexes('REAPER') then
    Result := 'Please save your REAPER project and close REAPER before updating Triceratops.';
end;
