#include "generated\version.iss"

[Setup]
AppId={{50E93A68-4FCA-4A45-9C54-370AA4CFE1D6}
AppName=Agent Skills MarketMaker
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\AgentSkills-MarketMaker
DefaultGroupName=Agent Skills MarketMaker
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\dist
OutputBaseFilename=agentskills-marketmaker-{#AppVersion}-setup
Compression=lzma2
SolidCompression=yes
ArchiveExtraction=full
WizardStyle=modern
CloseApplications=no
UninstallDisplayIcon={app}\runtime\pythonw.exe

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

; Inno downloads, verifies and extracts every dependency at installation time.
#include "generated\downloads.iss"

[Files]
Source: "..\build\app-{#AppVersion}\*"; DestDir: "{app}\runtime\Lib\site-packages"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "python312._pth"; DestDir: "{app}\runtime"; Flags: ignoreversion
Source: "launch.pyw"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "generated\payloads.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Agent Skills MarketMaker"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-B ""{app}\launch.pyw"""; WorkingDir: "{app}"
Name: "{autodesktop}\Agent Skills MarketMaker"; Filename: "{app}\runtime\pythonw.exe"; Parameters: "-B ""{app}\launch.pyw"""; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: "-B ""{app}\launch.pyw"""; WorkingDir: "{app}"; Description: "Launch Agent Skills MarketMaker"; Flags: nowait postinstall skipifsilent
