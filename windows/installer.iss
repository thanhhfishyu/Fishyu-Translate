#define AppName "Fishyu Translate for Windows"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6B2E4C1A-6F8B-4E57-9C1E-2F6A9D3B7E41}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=thanhhfishyu
AppPublisherURL=https://github.com/thanhhfishyu/Fishyu-Translate
DefaultDirName={localappdata}\Programs\Fishyu Translate
DefaultGroupName=Fishyu Translate
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=out
OutputBaseFilename=FishyuTranslate-for-Windows-Setup-v{#AppVersion}
SetupIconFile=assets\app_icon.ico
UninstallDisplayIcon={app}\FishyuTranslate.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
CloseApplications=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng ngoài màn hình Desktop"; GroupDescription: "Tuỳ chọn:"

[Files]
Source: "dist\FishyuTranslate\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Fishyu Translate"; Filename: "{app}\FishyuTranslate.exe"
Name: "{autodesktop}\Fishyu Translate"; Filename: "{app}\FishyuTranslate.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FishyuTranslate.exe"; Description: "Mở Fishyu Translate"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM FishyuTranslate.exe /F"; Flags: runhidden; RunOnceId: "KillApp"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
