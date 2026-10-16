Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "nsDialogs.nsh"
!ifndef PAYLOAD
  !error "Define PAYLOAD as the verified one-folder build directory"
!endif
!ifndef PORTABLE
  !error "Define PORTABLE as the verified single-file portable EXE"
!endif
!ifndef OUTPUT
  !error "Define OUTPUT as the installer output path"
!endif
!ifndef UNINSTALL_INCLUDE
  !error "Define UNINSTALL_INCLUDE as the generated file-removal manifest"
!endif
Name "Orvanta Video Downloader"
OutFile "${OUTPUT}"
InstallDir "$EXEDIR\Orvanta Video Downloader"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32
Icon "..\assets\app-icon.ico"
UninstallIcon "..\assets\app-icon.ico"
VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName" "Orvanta Video Downloader"
VIAddVersionKey "CompanyName" "Orvanta - Ahmed Eladwy"
VIAddVersionKey "FileDescription" "Orvanta Video Downloader Setup"
VIAddVersionKey "FileVersion" "1.0.0"
VIAddVersionKey "LegalCopyright" "Ahmed Eladwy"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\OrvantaVideoDownloader.exe"
!define MUI_FINISHPAGE_RUN_NOTCHECKED
!insertmacro MUI_PAGE_WELCOME
Page custom ModePage ModeLeave
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Var TestMode
Var Mode
Var PortableRadio
Var InstalledRadio
Var ModeDialog
Var PreviousMode

!macro ReadTestMode
  StrCpy $TestMode "0"
  ${GetParameters} $R0
  ${GetOptions} $R0 "/TESTMODE=" $TestMode
  SetShellVarContext current
  SetRegView 64
!macroend

Function .onInit
  !insertmacro ReadTestMode
  StrCpy $Mode "portable"
  ClearErrors
  ${GetOptions} $R0 "/MODE=" $R1
  ${IfNot} ${Errors}
    StrCpy $Mode $R1
  ${EndIf}
  ${If} $Mode != "portable"
  ${AndIf} $Mode != "installed"
    MessageBox MB_ICONSTOP "Use /MODE=portable or /MODE=installed." /SD IDOK
    Abort
  ${EndIf}
  StrCpy $PreviousMode $Mode
  ; NSIS has already applied /D to $INSTDIR and hides it from GetParameters.
  ; Preserve an explicit destination; only replace the untouched default.
  ${If} $Mode == "installed"
  ${AndIf} $INSTDIR == "$EXEDIR\Orvanta Video Downloader"
    StrCpy $INSTDIR "$LOCALAPPDATA\Programs\Orvanta\VideoDownloader"
    ReadRegStr $R2 HKCU "Software\Orvanta\VideoDownloader" "InstallDir"
    ${If} $R2 != ""
      StrCpy $INSTDIR $R2
    ${EndIf}
  ${EndIf}
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "This app requires 64-bit Windows." /SD IDOK
    Abort
  ${EndIf}
FunctionEnd

Function ModePage
  !insertmacro MUI_HEADER_TEXT "Choose how to use the app" "Portable is recommended. Both options include all download features."
  nsDialogs::Create 1018
  Pop $ModeDialog
  ${NSD_CreateRadioButton} 0 8u 100% 16u "Portable EXE (recommended)"
  Pop $PortableRadio
  ${NSD_CreateLabel} 12u 28u 95% 32u "Extract one EXE to your chosen folder. Copy it to another PC to run. Settings and history stay in this Windows user's AppData. Startup can take a few seconds."
  Pop $0
  ${NSD_CreateRadioButton} 0 76u 100% 16u "Install for this Windows user"
  Pop $InstalledRadio
  ${NSD_CreateLabel} 12u 96u 95% 32u "Add a Start menu shortcut and Windows uninstall entry. Keep settings and history in AppData."
  Pop $0
  ${If} $Mode == "portable"
    ${NSD_Check} $PortableRadio
  ${Else}
    ${NSD_Check} $InstalledRadio
  ${EndIf}
  nsDialogs::Show
FunctionEnd

Function ModeLeave
  ${NSD_GetState} $PortableRadio $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $Mode "portable"
  ${Else}
    StrCpy $Mode "installed"
  ${EndIf}
  ${If} $Mode != $PreviousMode
    ${If} $Mode == "portable"
      StrCpy $INSTDIR "$PROFILE\Orvanta Video Downloader"
    ${Else}
      StrCpy $INSTDIR "$LOCALAPPDATA\Programs\Orvanta\VideoDownloader"
    ${EndIf}
    StrCpy $PreviousMode $Mode
  ${EndIf}
FunctionEnd

Function un.onInit
  !insertmacro ReadTestMode
  IfFileExists "$INSTDIR\OrvantaVideoDownloader.exe" un_check_running un_ready
  un_check_running:
    ClearErrors
    FileOpen $0 "$INSTDIR\OrvantaVideoDownloader.exe" a
    IfErrors un_is_running un_close_handle
  un_is_running:
    MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION "Close the downloader before uninstalling it." /SD IDCANCEL IDOK un_check_running
    Abort
  un_close_handle:
    FileClose $0
  un_ready:
FunctionEnd

Section "Prepare app"
  ; Do not switch an existing folder between modes and strand its user data.
  ${If} $Mode == "portable"
    IfFileExists "$INSTDIR\Uninstall.exe" mode_conflict 0
    IfFileExists "$INSTDIR\portable.ini" mode_conflict 0
    IfFileExists "$INSTDIR\_internal\*.*" mode_conflict mode_ready
  ${Else}
    IfFileExists "$INSTDIR\portable.ini" mode_conflict 0
    IfFileExists "$INSTDIR\OrvantaVideoDownloader.exe" 0 mode_ready
    IfFileExists "$INSTDIR\Uninstall.exe" mode_ready mode_conflict
  ${EndIf}
  mode_conflict:
    MessageBox MB_ICONSTOP "This folder contains a different app format. Choose a separate folder. Existing app files and data will be kept." /SD IDOK
    SetErrorLevel 2
    Quit
  mode_ready:
  IfFileExists "$INSTDIR\OrvantaVideoDownloader.exe" check_running copy_payload
  check_running:
    ClearErrors
    FileOpen $0 "$INSTDIR\OrvantaVideoDownloader.exe" a
    IfErrors is_running close_handle
  is_running:
    MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION "Close the installed downloader before updating it." /SD IDCANCEL IDOK check_running
    Abort
  close_handle:
    FileClose $0
  copy_payload:
  SetOutPath "$INSTDIR"
  ${If} $Mode == "portable"
    File /oname=OrvantaVideoDownloader.exe "${PORTABLE}"
    Goto setup_done
  ${EndIf}
  File /r "${PAYLOAD}\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  ${If} $TestMode != "1"
    CreateShortcut "$SMPROGRAMS\Orvanta Video Downloader.lnk" "$INSTDIR\OrvantaVideoDownloader.exe"
    WriteRegStr HKCU "Software\Orvanta\VideoDownloader" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OrvantaVideoDownloader" "DisplayName" "Orvanta Video Downloader"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OrvantaVideoDownloader" "Publisher" "Orvanta - Ahmed Eladwy"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OrvantaVideoDownloader" "DisplayVersion" "1.0.0"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OrvantaVideoDownloader" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OrvantaVideoDownloader" "DisplayIcon" "$INSTDIR\OrvantaVideoDownloader.exe,0"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OrvantaVideoDownloader" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OrvantaVideoDownloader" "QuietUninstallString" '$\"$INSTDIR\Uninstall.exe$\" /S'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OrvantaVideoDownloader" "HelpLink" "mailto:eladwy.ahmed@gmail.com"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OrvantaVideoDownloader" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OrvantaVideoDownloader" "NoRepair" 1
  ${EndIf}
  setup_done:
SectionEnd

Section "Uninstall"
  ; Only remove files from this build's manifest. Never recursively delete the
  ; user's chosen folder or touch download/history data in AppData.
  !include "${UNINSTALL_INCLUDE}"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  ${If} $TestMode != "1"
    Delete "$SMPROGRAMS\Orvanta Video Downloader.lnk"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\OrvantaVideoDownloader"
    DeleteRegKey HKCU "Software\Orvanta\VideoDownloader"
  ${EndIf}
SectionEnd
