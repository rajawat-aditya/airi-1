; ============================================================
;  Airi — AI Desktop Assistant  |  NSIS Installer
;  © 2026 Slew Inc. All rights reserved.
;
;  STRATEGY: Files are NOT embedded in the installer EXE.
;  Instead this installer copies from a "payload" folder
;  that sits next to the installer EXE at runtime.
;
;  Distribution layout:
;    Airi-Setup-0.1.0\
;      Airi-Setup-0.1.0.exe   ← this installer
;      payload\               ← copy of build\win-unpacked\
;
;  Build:
;    makensis installer\airi-installer.nsi
; ============================================================

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"

SetCompress off

; ── Metadata ─────────────────────────────────────────────────
!define APP_NAME        "Airi"
!define APP_VERSION     "0.1.0"
!define APP_PUBLISHER   "Slew Inc."
!define APP_URL         "https://airi.app"
!define APP_EXE         "Airi.exe"
!define APP_ID          "com.airi.app"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}"
!define MUI_ICON        "..\public\logo.ico"
!define MUI_UNICON      "..\public\logo.ico"

; ── Output ───────────────────────────────────────────────────
Name             "${APP_NAME} ${APP_VERSION}"
OutFile          "..\build\Airi-Setup-${APP_VERSION}.exe"
InstallDir       "$PROGRAMFILES64\${APP_NAME}"
InstallDirRegKey HKLM "${UNINSTALL_KEY}" "InstallLocation"
RequestExecutionLevel admin

; ── MUI ──────────────────────────────────────────────────────
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE    "Welcome to ${APP_NAME} Setup"
!define MUI_WELCOMEPAGE_TEXT     "This will install ${APP_NAME} ${APP_VERSION} on your computer.$\r$\n$\r$\nAiri is your AI-powered desktop assistant.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN       "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT  "Launch ${APP_NAME}"
!define MUI_FINISHPAGE_LINK      "${APP_URL}"
!define MUI_FINISHPAGE_LINK_LOCATION "${APP_URL}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE    "..\LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ── Version info ─────────────────────────────────────────────
VIProductVersion "0.1.0.0"
VIAddVersionKey "ProductName"     "${APP_NAME}"
VIAddVersionKey "ProductVersion"  "${APP_VERSION}"
VIAddVersionKey "CompanyName"     "${APP_PUBLISHER}"
VIAddVersionKey "LegalCopyright"  "© 2026 Slew Inc. All rights reserved."
VIAddVersionKey "FileDescription" "${APP_NAME} Installer"
VIAddVersionKey "FileVersion"     "0.1.0.0"

; ═════════════════════════════════════════════════════════════
;  INSTALL
; ═════════════════════════════════════════════════════════════
Section "Install" SEC_MAIN

  ; Locate the payload folder next to the running installer EXE
  Push $R0
  GetFullPathName $R0 "$EXEDIR\payload"

  ${If} ${FileExists} "$R0\${APP_EXE}"
    ; payload is next to the installer — good
  ${Else}
    MessageBox MB_OK|MB_ICONSTOP \
      "Cannot find the payload folder.$\r$\n$\r$\nExpected: $R0$\r$\n$\r$\nMake sure '${APP_NAME} ${APP_VERSION}' folder structure is intact." \
      /SD IDOK
    Abort
  ${EndIf}

  SetOutPath "$INSTDIR"
  SetOverwrite on

  ; ── Copy payload using xcopy (avoids NSIS 2 GB data block limit) ──
  DetailPrint "Copying application files..."
  nsExec::ExecToLog 'xcopy "$R0\*" "$INSTDIR\" /E /I /H /Y /Q'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_OK|MB_ICONSTOP "File copy failed (xcopy exit code $0)."
    Abort
  ${EndIf}

  Pop $R0

  ; ── Uninstaller ──────────────────────────────────────────
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; ── Registry ─────────────────────────────────────────────
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayName"          "${APP_NAME}"
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayVersion"       "${APP_VERSION}"
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "Publisher"            "${APP_PUBLISHER}"
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "URLInfoAbout"         "${APP_URL}"
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "InstallLocation"      "$INSTDIR"
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "UninstallString"      '"$INSTDIR\Uninstall.exe"'
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayIcon"          '"$INSTDIR\${APP_EXE}"'
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify"             1
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair"             1

  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "EstimatedSize" "$0"

  ; ── Shortcuts ────────────────────────────────────────────
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
                 "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" \
                 "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
                 "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0

SectionEnd

; ═════════════════════════════════════════════════════════════
;  UNINSTALL
; ═════════════════════════════════════════════════════════════
Section "Uninstall"

  ExecWait 'taskkill /F /IM "${APP_EXE}"' $0

  RMDir /r "$INSTDIR\locales"
  RMDir /r "$INSTDIR\resources"
  Delete "$INSTDIR\*.exe"
  Delete "$INSTDIR\*.dll"
  Delete "$INSTDIR\*.pak"
  Delete "$INSTDIR\*.dat"
  Delete "$INSTDIR\*.bin"
  Delete "$INSTDIR\*.html"
  Delete "$INSTDIR\*.json"
  Delete "$INSTDIR\*.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir  "$INSTDIR"

  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk"
  RMDir  "$SMPROGRAMS\${APP_NAME}"
  Delete "$DESKTOP\${APP_NAME}.lnk"

  DeleteRegKey HKLM "${UNINSTALL_KEY}"

SectionEnd

; ═════════════════════════════════════════════════════════════
;  CALLBACKS
; ═════════════════════════════════════════════════════════════
Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_OK|MB_ICONSTOP \
      "This application requires a 64-bit version of Windows."
    Abort
  ${EndIf}
FunctionEnd
