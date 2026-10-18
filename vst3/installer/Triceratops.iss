#define AppVersion "1.0.2"
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
OutputBaseFilename=Triceratops-1.0.2-Windows-x64-Setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
MinVersion=10.0
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayName=Triceratops Music Agent 1.0.2
SetupLogging=yes
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
[Files]
Source: "{#PayloadRoot}\Triceratops.vst3\*"; DestDir: "{commoncf64}\VST3\Triceratops.vst3"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo"
Source: "{#PayloadRoot}\python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadRoot}\llama-cpp\*"; DestDir: "{app}\llama-cpp"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\package\tools\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
[InstallDelete]
Type: filesandordirs; Name: "{app}\ollama"
Type: files; Name: "{app}\backend\text2music\agent\app.py"
Type: files; Name: "{app}\backend\text2music\agent\service.py"
Type: files; Name: "{app}\backend\text2music\agent\workflow.py"
Type: files; Name: "{app}\backend\text2music\agent\reaper_bridge.py"
Type: files; Name: "{app}\backend\text2music\agent\router.py"
Type: files; Name: "{app}\backend\text2music\agent\launch_reaper_agent.sh"
Type: files; Name: "{app}\backend\text2music\agent\launch_reaper_job.sh"
Type: files; Name: "{app}\backend\text2music\agent\launch_reaper_worker.sh"
Type: files; Name: "{app}\backend\text2music\agent\install_symbolic_models.sh"
Type: files; Name: "{app}\backend\text2music\agent\import_trigger.lua"
Type: files; Name: "{app}\backend\text2music\agent\reaper_import_trigger.lua"
Type: filesandordirs; Name: "{app}\backend\text2music\agent\__pycache__"

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
