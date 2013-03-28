; Script generated by the Inno Setup Script Wizard.
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING INNO SETUP SCRIPT FILES!

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{1257EE3E-5CF2-48E7-A7A2-AAE958053ECF}
AppName=Star Edit
AppVerName=Star Edit 1.0
AppPublisher=Michael Fogleman
AppPublisherURL=http://www.star-rocket.com/
AppSupportURL=http://www.star-rocket.com/
AppUpdatesURL=http://www.star-rocket.com/
DefaultDirName={pf}\Star Edit
DefaultGroupName=Star Edit
AllowNoIcons=yes
OutputDir=installer
OutputBaseFilename=star-edit-installer
Compression=lzma
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
Name: "{app}"; Permissions: everyone-modify

[Files]
Source: "dist\star-edit.exe"; DestDir: "{app}"; Flags: ignoreversion; Permissions: everyone-readexec
Source: "dist\w9xpopen.exe"; DestDir: "{app}"; Flags: ignoreversion; Permissions: everyone-readexec
Source: "dist\library.zip"; DestDir: "{app}"; Flags: ignoreversion; Permissions: everyone-readexec
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\Star Edit"; Filename: "{app}\star-edit.exe"; WorkingDir: "{app}";
Name: "{group}\{cm:UninstallProgram,Star Edit}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Star Edit"; Filename: "{app}\star-edit.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\Star Edit"; Filename: "{app}\star-edit.exe"; WorkingDir: "{app}"; Tasks: quicklaunchicon

[Registry]
Root: HKCR; Subkey: ".star"; ValueType: string; ValueName: ""; ValueData: "StarEditFile"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "StarEditFile"; ValueType: string; ValueName: ""; ValueData: "Star Edit"; Flags: uninsdeletekey
Root: HKCR; Subkey: "StarEditFile\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\star-edit.exe,0"
Root: HKCR; Subkey: "StarEditFile\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\star-edit.exe"" ""%1"""

[Run]
Filename: "{app}\star-edit.exe"; Description: "{cm:LaunchProgram,Star Edit}"; Flags: nowait postinstall
