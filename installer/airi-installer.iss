; ============================================================
;  Airi — AI Desktop Assistant
;  Inno Setup Script
;  © 2026 Slew Inc. All rights reserved.
;
;  Microsoft Store EXE submission requirements:
;    Silent install:   Airi-Setup-0.1.0.exe /VERYSILENT /SUPPRESSMSGBOXES
;    Silent uninstall: "%ProgramFiles%\Airi\Uninstall.exe" /VERYSILENT /SUPPRESSMSGBOXES
;
;  Build:
;    iscc installer\airi-installer.iss
; ============================================================

#define AppName        "Airi"
#define AppVersion     "0.1.0"
#define AppPublisher   "Slew Inc."
#define AppURL         "https://airi.app"
#define AppExeName     "Airi.exe"
#define AppId          "com.airi.app"
#define BuildDir       "..\build\win-unpacked"
#define OutputDir      "..\build"

[Setup]
AppId                    = {{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName                  = {#AppName}
AppVersion               = {#AppVersion}
AppVerName               = {#AppName} {#AppVersion}
AppPublisher             = {#AppPublisher}
AppPublisherURL          = {#AppURL}
AppSupportURL            = {#AppURL}
AppUpdatesURL            = {#AppURL}
AppCopyright             = Copyright © 2026 Slew Inc. All rights reserved.

; Install to Program Files (required for Store EXE submission)
DefaultDirName           = {autopf}\{#AppName}
DefaultGroupName         = {#AppName}
DisableProgramGroupPage  = yes

; Output
OutputDir                = {#OutputDir}
OutputBaseFilename       = Airi-Setup-{#AppVersion}
SetupIconFile            = ..\public\logo.ico

; Compression — use lzma2/ultra64 for best ratio on large installs
Compression              = lzma2/ultra64
SolidCompression         = yes
LZMAUseSeparateProcess   = yes
LZMANumBlockThreads      = 4

; UI
WizardStyle              = modern
WizardResizable          = no
ShowLanguageDialog       = no

; Privileges — required for Program Files install
PrivilegesRequired       = admin
PrivilegesRequiredOverridesAllowed = commandline

; Misc
DisableWelcomePage       = no
DisableReadyPage         = no
DisableFinishedPage      = no
AllowNoIcons             = yes
UninstallDisplayIcon     = {app}\{#AppExeName}
UninstallDisplayName     = {#AppName}

; No reboot (Store requirement)
RestartIfNeededByRun     = no
; Prevent any reboot prompts — required for Store certification
CloseApplications        = yes
CloseApplicationsFilter  = *.exe
RestartApplications      = no

; Minimum Windows version: Windows 10 (Store requirement)
MinVersion               = 10.0.17763

; Architecture
ArchitecturesAllowed            = x64compatible
ArchitecturesInstallIn64BitMode = x64compatible

; License
LicenseFile              = ..\LICENSE.txt

; Version info on the setup EXE itself
VersionInfoVersion       = 0.1.0.0
VersionInfoCompany       = {#AppPublisher}
VersionInfoDescription   = {#AppName} Installer
VersionInfoCopyright     = Copyright © 2026 Slew Inc.
VersionInfoProductName   = {#AppName}
VersionInfoProductVersion= {#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Root Electron files
Source: "{#BuildDir}\Airi.exe";                    DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\chrome_100_percent.pak";      DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\chrome_200_percent.pak";      DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\d3dcompiler_47.dll";          DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\dxcompiler.dll";              DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\dxil.dll";                    DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\ffmpeg.dll";                  DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\icudtl.dat";                  DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\libEGL.dll";                  DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\libGLESv2.dll";               DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\LICENSE.electron.txt";        DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\LICENSES.chromium.html";      DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\resources.pak";               DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\snapshot_blob.bin";           DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\v8_context_snapshot.bin";     DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\vk_swiftshader_icd.json";     DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\vk_swiftshader.dll";          DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\vulkan-1.dll";                DestDir: "{app}"; Flags: ignoreversion

; Locales
Source: "{#BuildDir}\locales\*"; DestDir: "{app}\locales"; Flags: ignoreversion recursesubdirs createallsubdirs

; Resources
Source: "{#BuildDir}\resources\app.asar";          DestDir: "{app}\resources"; Flags: ignoreversion
Source: "{#BuildDir}\resources\.env.local";        DestDir: "{app}\resources"; Flags: ignoreversion
Source: "{#BuildDir}\resources\app.asar.unpacked\*"; DestDir: "{app}\resources\app.asar.unpacked"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#BuildDir}\resources\airi-agent\*";      DestDir: "{app}\resources\airi-agent";          Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#BuildDir}\resources\deps\*";            DestDir: "{app}\resources\deps";                Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";          Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";    Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Offer to launch after install (skipped in silent mode)
Filename: "{app}\{#AppExeName}"; \
  Description: "Launch {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kill running instance before uninstall
Filename: "taskkill.exe"; Parameters: "/F /IM ""{#AppExeName}"""; \
  Flags: runhidden skipifdoesntexist; RunOnceId: "KillAiri"

[Code]
// ── Kill any running instance before install/upgrade ──────────
procedure KillRunningInstance();
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM "' + '{#AppExeName}' + '"', '', SW_HIDE,
       ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    KillRunningInstance();
end;
