[Setup]
AppId={{D2751942-1E3B-4CFB-9233-984CC81C62A4}
AppName=CyberForge
AppVersion={#ApplicationVersion}
AppPublisher=CyberForge
DefaultDirName={localappdata}\Programs\CyberForge
DefaultGroupName=CyberForge
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.22000
DisableProgramGroupPage=yes
DisableDirPage=yes
CloseApplications=no
RestartApplications=no
AppMutex=Local\CyberForge-Release-v1
SetupMutex=Local\CyberForge-Setup-v1
Compression=lzma2/fast
SolidCompression=yes
OutputDir={#ReleaseDir}
OutputBaseFilename=CyberForge-{#ApplicationVersion}-windows-x64-setup
UninstallDisplayIcon={app}\app-{#Revision}\CyberForge.exe
WizardStyle=modern

[Languages]
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}\app-{#Revision}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CyberForge"; Filename: "{app}\app-{#Revision}\CyberForge.exe"; WorkingDir: "{app}\app-{#Revision}"
Name: "{group}\Аварійне відновлення CyberForge"; Filename: "{app}\app-{#Revision}\CyberForge.exe"; Parameters: "--recovery"; WorkingDir: "{app}\app-{#Revision}"
