; Easy Theme Creator installer. Build with:  python installer\build.py
; (it stages the files and passes Stage, OutDir and AppVersion to ISCC).

#ifndef AppVersion
  #define AppVersion "2.0"
#endif

[Setup]
AppId={{6F3C2B8E-5A1D-4E7B-9C2F-EA5E7C0D2B11}
AppName=Easy Theme Creator
AppVersion={#AppVersion}
AppVerName=Easy Theme Creator {#AppVersion}
AppPublisher=Easy Theme Creator
DefaultDirName={autopf}\Easy Theme Creator
DefaultGroupName=Easy Theme Creator
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
OutputDir={#OutDir}
OutputBaseFilename=Easy Theme Creator Setup
SetupIconFile={#Stage}\app\app.ico
UninstallDisplayIcon={app}\app\app.ico
UninstallDisplayName=Easy Theme Creator
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
InfoBeforeFile={#Stage}\README.txt
CloseApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "restorepoint"; Description: "Make a System Restore point first (recommended)"; GroupDescription: "Safety:"
Name: "secureux"; Description: "SecureUxTheme - lets Windows load custom window skins (needed for Windows skin, Metal buttons, Armor Explorer)"; GroupDescription: "Helpers (free, open source):"; Check: not SecureUxInstalled
Name: "windhawk"; Description: "Windhawk + 3 mods - metal taskbar, Alien Start button, Armor Explorer and a dark Control Panel"; GroupDescription: "Helpers (free, open source):"; Check: not WindhawkModsReady
Name: "openshell"; Description: "Open-Shell (Start menu only) - the Windows 7 Start menu in the armor skin"; GroupDescription: "Helpers (free, open source):"; Check: not OpenShellInstalled
Name: "desktopicon"; Description: "Desktop shortcut"; GroupDescription: "Shortcuts:"

[Dirs]
; The app keeps generated skins, icons and the Control Panel redirect here; normal
; users must be able to write it even though the installer (admin) creates it.
Name: "{commonappdata}\EasyThemeCreator"; Permissions: users-modify
Name: "{commonappdata}\EasyThemeCreator\redirect"; Permissions: users-modify

[Files]
Source: "{#Stage}\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs ignoreversion
Source: "{#Stage}\python\*"; DestDir: "{app}\python"; Flags: recursesubdirs ignoreversion
Source: "{#Stage}\licenses\*"; DestDir: "{app}\licenses"; Flags: recursesubdirs ignoreversion
Source: "{#Stage}\README.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "{#Stage}\deps\SecureUxTheme_x64.msi"; DestDir: "{tmp}"; Tasks: secureux; Flags: deleteafterinstall
Source: "{#Stage}\deps\OpenShellSetup64_4_4_198.msi"; DestDir: "{tmp}"; Tasks: openshell; Flags: deleteafterinstall
Source: "{#Stage}\deps\windhawk_setup.exe"; DestDir: "{tmp}"; Tasks: windhawk; Flags: deleteafterinstall
Source: "{#Stage}\deps\setup-windhawk-mod.ps1"; DestDir: "{tmp}"; Tasks: windhawk; Flags: deleteafterinstall
Source: "{#Stage}\deps\windhawk-mod\*"; DestDir: "{tmp}\windhawk-mod"; Tasks: windhawk; Flags: recursesubdirs deleteafterinstall

[Registry]
; Open-Shell would show its settings window on the first Start click; the app sets it up instead.
Root: HKCU; Subkey: "Software\OpenShell\StartMenu"; ValueType: dword; ValueName: "ShowedStyle2"; ValueData: 1; Tasks: openshell
; SecureUxTheme only works after a restart: then the app opens by itself, once, ready to use.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\RunOnce"; ValueType: string; ValueName: "EasyThemeCreator"; ValueData: """{app}\python\pythonw.exe"" ""{app}\app\launch.pyw"""; Tasks: secureux; Flags: uninsdeletevalue

[Icons]
Name: "{autoprograms}\Easy Theme Creator"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launch.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\app\app.ico"
Name: "{autodesktop}\Easy Theme Creator"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launch.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\app\app.ico"; Tasks: desktopicon

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Enable-ComputerRestore -Drive $env:SystemDrive -EA SilentlyContinue; Checkpoint-Computer -Description 'Before Easy Theme Creator' -RestorePointType MODIFY_SETTINGS -EA SilentlyContinue"""; StatusMsg: "{code:StepStatus|restore}"; Tasks: restorepoint; BeforeInstall: BeginStep('restore'); Flags: 64bit runhidden waituntilterminated
Filename: "{sys}\msiexec.exe"; Parameters: "/i ""{tmp}\SecureUxTheme_x64.msi"" /qn /norestart"; StatusMsg: "{code:StepStatus|secureux}"; Tasks: secureux; BeforeInstall: BeginStep('secureux'); Flags: 64bit waituntilterminated
Filename: "{tmp}\windhawk_setup.exe"; Parameters: "/S /STANDARD"; StatusMsg: "{code:StepStatus|windhawk}"; Tasks: windhawk; Check: not WindhawkInstalled; BeforeInstall: BeginStep('windhawk'); Flags: waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{tmp}\setup-windhawk-mod.ps1"" -ModDir ""{tmp}\windhawk-mod"""; StatusMsg: "{code:StepStatus|mods}"; Tasks: windhawk; BeforeInstall: BeginStep('mods'); Flags: 64bit runhidden waituntilterminated
Filename: "{sys}\msiexec.exe"; Parameters: "/i ""{tmp}\OpenShellSetup64_4_4_198.msi"" ADDLOCAL=StartMenu /qn /norestart"; StatusMsg: "{code:StepStatus|openshell}"; Tasks: openshell; BeforeInstall: BeginStep('openshell'); Flags: 64bit waituntilterminated
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""$s = Join-Path $env:ProgramFiles 'Open-Shell\Skins'; $d = Join-Path $s 'Easy Theme Armor.skin7'; if ((Test-Path (Join-Path $s 'Midnight.skin7')) -and -not (Test-Path $d)) {{ Copy-Item (Join-Path $s 'Midnight.skin7') $d }; if (Test-Path $d) {{ icacls $d /grant '*S-1-5-32-545:M' | Out-Null }"""; StatusMsg: "{code:StepStatus|skin}"; BeforeInstall: BeginStep('skin'); AfterInstall: FinishSteps; Flags: 64bit runhidden waituntilterminated
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launch.pyw"""; WorkingDir: "{app}\app"; Description: "Open Easy Theme Creator now"; Flags: postinstall nowait skipifsilent runasoriginaluser

[UninstallRun]
; Put the old Windows look back before the files go (same as pressing Undo).
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launch.pyw"" --undo"; WorkingDir: "{app}\app"; RunOnceId: "EtcUndo"; Flags: runhidden waituntilterminated

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app\__pycache__"
Type: filesandordirs; Name: "{commonappdata}\EasyThemeCreator"
; our Start menu skin (Open-Shell itself stays installed)
Type: files; Name: "{commonpf64}\Open-Shell\Skins\Easy Theme Armor.skin7"

[Messages]
FinishedLabel=Easy Theme Creator is installed.
; shown instead when SecureUxTheme was just installed (NeedRestart)
FinishedRestartLabel=Easy Theme Creator is installed.%n%nWindows needs to restart once so the new window skin can load. After the restart, Easy Theme Creator opens by itself - pick a picture and press Apply.%n%nRestart now?
FinishedRestartMessage=Easy Theme Creator is installed.%n%nWindows needs to restart once so the new window skin can load. After the restart, Easy Theme Creator opens by itself.%n%nRestart now?
YesRadio=&Yes, restart now (recommended)
NoRadio=&No, I will restart later
; Inno's own uninstall question (skipped by silent uninstalls - a [Code] MsgBox never is)
ConfirmUninstall=Uninstalling puts your old Windows look back first (like pressing Undo).%n%nSecureUxTheme, Windhawk and Open-Shell stay installed; remove them in Settings > Apps if you like.%n%nUninstall %1 now?

[Code]
function SecureUxInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{sys}\SecureUxTheme4.dll'));
end;

function WindhawkInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{commonpf64}\Windhawk\windhawk.exe'));
end;

function OpenShellInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{commonpf64}\Open-Shell\StartMenu.exe'));
end;

function WindhawkModsReady: Boolean;
begin
  Result := WindhawkInstalled and
    RegKeyExists(HKLM64, 'SOFTWARE\Windhawk\Engine\Mods\icon-resource-redirect') and
    RegKeyExists(HKLM64, 'SOFTWARE\Windhawk\Engine\Mods\windows-11-taskbar-styler') and
    RegKeyExists(HKLM64, 'SOFTWARE\Windhawk\Engine\Mods\windows-11-file-explorer-styler') and
    RegKeyExists(HKLM64, 'SOFTWARE\Windhawk\Engine\Mods\easy-theme-creator-standard-colors');
end;

const
  V1_KEY = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\EasyThemeCreator';

{ ---------- The installing page: what is happening, how far, how long ----------
  Under Inno's step line and its moving bar: an overall bar with a percentage, the
  time so far and roughly the time left, and a checklist of the steps. A timer
  refreshes it twice a second (Inno keeps handling window messages while a helper
  runs, so the timer keeps firing). Step lengths are rough, measured estimates; a
  step that runs longer creeps towards its end and says it is still working. }
var
  StepKey, StepName, StepDoing, StepNote: array of String;
  StepSecs: array of Integer;
  StepLabels: array of TNewStaticText;
  StepCount, CurIdx: Integer;
  StepStart, InstallStart: LongWord;
  FilesFrac: Extended;
  OverallLabel: TNewStaticText;
  OverallBar: TNewProgressBar;
  ProgressTimer: LongWord;

function GetTickCount: LongWord; external 'GetTickCount@kernel32.dll stdcall';
function SetTimer(hWnd, nIDEvent, uElapse, lpTimerFunc: LongWord): LongWord; external 'SetTimer@user32.dll stdcall';
function KillTimer(hWnd, uIDEvent: LongWord): LongWord; external 'KillTimer@user32.dll stdcall';

procedure AddStep(Key, Name, Doing, Note: String; Secs: Integer);
begin
  SetArrayLength(StepKey, StepCount + 1);
  SetArrayLength(StepName, StepCount + 1);
  SetArrayLength(StepDoing, StepCount + 1);
  SetArrayLength(StepNote, StepCount + 1);
  SetArrayLength(StepSecs, StepCount + 1);
  StepKey[StepCount] := Key;
  StepName[StepCount] := Name;
  StepDoing[StepCount] := Doing;
  StepNote[StepCount] := Note;
  StepSecs[StepCount] := Secs;
  StepCount := StepCount + 1;
end;

{ Only the steps that will really run, so "Step x of y" adds up. }
procedure BuildSteps(HasV1: Boolean);
begin
  StepCount := 0;
  if HasV1 then
    AddStep('v1', 'Remove the old version', 'Removing the old version of Easy Theme Creator...',
      'The old version is replaced by this one.', 5);
  AddStep('files', 'Copy the app files', 'Copying the app files...', '', 15);
  if WizardIsTaskSelected('restorepoint') then
    AddStep('restore', 'Make a System Restore point', 'Making a System Restore point...',
      'A safety point to go back to, just in case.', 20);
  if WizardIsTaskSelected('secureux') then
    AddStep('secureux', 'Install SecureUxTheme', 'Installing SecureUxTheme...',
      'Lets Windows load the window skin the app makes. Can take a minute or two.', 60);
  if WizardIsTaskSelected('windhawk') and not WindhawkInstalled then
    AddStep('windhawk', 'Install Windhawk', 'Installing Windhawk...',
      'Runs the taskbar, Start button and Explorer looks.', 15);
  if WizardIsTaskSelected('windhawk') then
    AddStep('mods', 'Set up the Windhawk mods', 'Setting up the Windhawk mods...',
      'Metal taskbar, Alien Start button, Armor Explorer, dark Control Panel.', 6);
  if WizardIsTaskSelected('openshell') then
    AddStep('openshell', 'Install the Open-Shell Start menu', 'Installing the Open-Shell Start menu...',
      'The Windows 7 Start menu, in the armor skin. Can take a minute or two.', 60);
  AddStep('skin', 'Finish up', 'Finishing up...', '', 3);
end;

function StepIndex(Key: String): Integer;
var
  i: Integer;
begin
  Result := -1;
  for i := 0 to StepCount - 1 do
    if StepKey[i] = Key then
    begin
      Result := i;
      Exit;
    end;
end;

{ [Run] StatusMsg: "Step 3 of 7: Installing SecureUxTheme..." }
function StepStatus(Param: String): String;
var
  i: Integer;
begin
  i := StepIndex(Param);
  if i < 0 then
    Result := 'Working...'
  else
    Result := Format('Step %d of %d: %s', [i + 1, StepCount, StepDoing[i]]);
end;

function FmtTime(Secs: Integer): String;
begin
  Result := Format('%d:%.2d', [Secs div 60, Secs mod 60]);
end;

function TimeLeftText(Secs: Integer): String;
begin
  if Secs <= 10 then
    Result := 'almost done'
  else if Secs < 50 then
    Result := 'less than a minute left'
  else if Secs < 90 then
    Result := 'about a minute left'
  else
    Result := Format('about %d minutes left', [(Secs + 30) div 60]);
end;

{ done = green tick, now = bold arrow, still to come = grey }
procedure ShowChecklist;
var
  i: Integer;
begin
  for i := 0 to GetArrayLength(StepLabels) - 1 do
    if i < CurIdx then
    begin
      StepLabels[i].Caption := #$2713 + '  ' + StepName[i];
      StepLabels[i].Font.Style := [];
      StepLabels[i].Font.Color := clGreen;
    end
    else if i = CurIdx then
    begin
      StepLabels[i].Caption := #$25BA + '  ' + StepName[i];
      StepLabels[i].Font.Style := [fsBold];
      StepLabels[i].Font.Color := clWindowText;
    end
    else
    begin
      StepLabels[i].Caption := '      ' + StepName[i];
      StepLabels[i].Font.Style := [];
      StepLabels[i].Font.Color := clGrayText;
    end;
end;

procedure UpdateProgress;
var
  i, total, done, secs, elapsed, left, all: Integer;
  frac, pct: Extended;
begin
  if (OverallLabel = nil) or (CurIdx < 0) or (CurIdx >= StepCount) then
    Exit;
  total := 0;
  done := 0;
  left := 0;
  for i := 0 to StepCount - 1 do
  begin
    total := total + StepSecs[i];
    if i < CurIdx then
      done := done + StepSecs[i];
    if i > CurIdx then
      left := left + StepSecs[i];
  end;
  if total <= 0 then
    Exit;
  secs := StepSecs[CurIdx];
  elapsed := (GetTickCount - StepStart) div 1000;
  if StepKey[CurIdx] = 'files' then
  begin
    frac := FilesFrac;
    left := left + Round(secs * (1 - frac));
  end
  else
  begin
    frac := elapsed;                     { Extended first: Integer / Integer is cut to 0 here }
    frac := frac / secs;
    if frac > 0.9 then                    { creep towards 99%, never reach the end early }
      frac := 0.9 + 0.09 * (frac - 0.9) / (frac - 0.9 + 0.5);
    if elapsed < secs then
      left := left + secs - elapsed;
  end;
  pct := (done + secs * frac) / total;
  OverallBar.Position := Round(pct * 1000);
  all := (GetTickCount - InstallStart) div 1000;
  if (StepKey[CurIdx] <> 'files') and (elapsed > secs + 15) and (elapsed * 2 > secs * 3) then
    OverallLabel.Caption := Format('Overall: %d%%   ' + #$00B7 + '   %s so far   ' + #$00B7 +
      '   taking longer than usual - still working', [Round(pct * 100), FmtTime(all)])
  else
    OverallLabel.Caption := Format('Overall: %d%%   ' + #$00B7 + '   %s so far   ' + #$00B7 + '   %s', [Round(pct * 100), FmtTime(all), TimeLeftText(left)]);
end;

procedure ProgressTick(Arg1, Arg2, Arg3, Arg4: LongWord);
begin
  UpdateProgress;
end;

procedure CreateProgressControls;
var
  i, top, lineH: Integer;
  page: TNewNotebookPage;
begin
  page := WizardForm.InstallingPage;
  top := WizardForm.ProgressGauge.Top + WizardForm.ProgressGauge.Height + ScaleY(14);
  OverallLabel := TNewStaticText.Create(WizardForm);
  OverallLabel.Parent := page;
  OverallLabel.AutoSize := False;
  OverallLabel.Left := WizardForm.ProgressGauge.Left;
  OverallLabel.Top := top;
  OverallLabel.Width := WizardForm.ProgressGauge.Width;
  OverallLabel.Height := ScaleY(16);
  OverallLabel.Caption := 'Overall: 0%';
  top := top + ScaleY(19);
  OverallBar := TNewProgressBar.Create(WizardForm);
  OverallBar.Parent := page;
  OverallBar.Left := WizardForm.ProgressGauge.Left;
  OverallBar.Top := top;
  OverallBar.Width := WizardForm.ProgressGauge.Width;
  OverallBar.Height := ScaleY(10);
  OverallBar.Min := 0;
  OverallBar.Max := 1000;
  OverallBar.Position := 0;
  top := top + OverallBar.Height + ScaleY(12);
  lineH := ScaleY(18);
  if (StepCount > 0) and (top + StepCount * lineH > page.Height) then
    lineH := (page.Height - top) div StepCount;
  SetArrayLength(StepLabels, StepCount);
  for i := 0 to StepCount - 1 do
  begin
    StepLabels[i] := TNewStaticText.Create(WizardForm);
    StepLabels[i].Parent := page;
    StepLabels[i].Left := WizardForm.ProgressGauge.Left + ScaleX(4);
    StepLabels[i].Top := top + i * lineH;
  end;
end;

{ BeforeInstall of each helper step (and called for the first two steps). }
procedure BeginStep(Key: String);
var
  i: Integer;
begin
  i := StepIndex(Key);
  if i < 0 then
    Exit;
  CurIdx := i;
  StepStart := GetTickCount;
  if Key <> 'files' then                  { Inno draws the file copying itself }
  begin
    if WizardForm.ProgressGauge.Style <> npbstMarquee then
      WizardForm.ProgressGauge.Style := npbstMarquee;
    WizardForm.StatusLabel.Caption := StepStatus(Key);
    WizardForm.FilenameLabel.Caption := StepNote[i];
  end;
  ShowChecklist;
  UpdateProgress;
end;

{ AfterInstall of the last step, and once more after all steps. }
procedure FinishSteps;
begin
  if ProgressTimer <> 0 then
    KillTimer(0, ProgressTimer);
  ProgressTimer := 0;
  if OverallLabel = nil then
    Exit;
  CurIdx := StepCount;
  ShowChecklist;
  OverallBar.Position := 1000;
  OverallLabel.Caption := 'Overall: 100%   ' + #$00B7 + '   done in ' + FmtTime((GetTickCount - InstallStart) div 1000);
end;

{ The first version installed per user (NSIS). Remove it so there is one app. }
procedure RemoveVersion1;
var
  cmd: String;
  rc, i: Integer;
begin
  if not RegQueryStringValue(HKCU, V1_KEY, 'UninstallString', cmd) then
    Exit;
  Exec(RemoveQuotes(cmd), '/S', '', SW_HIDE, ewWaitUntilTerminated, rc);
  { the NSIS uninstaller re-launches itself from TEMP, so wait for it to finish }
  for i := 1 to 60 do
  begin
    if not RegKeyExists(HKCU, V1_KEY) then
      Exit;
    Sleep(500);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  cmd: String;
  hasV1: Boolean;
begin
  if CurStep = ssInstall then
  begin
    hasV1 := RegQueryStringValue(HKCU, V1_KEY, 'UninstallString', cmd);
    BuildSteps(hasV1);
    CreateProgressControls;
    InstallStart := GetTickCount;
    CurIdx := -1;
    ProgressTimer := SetTimer(0, 0, 500, CreateCallback(@ProgressTick));
    if hasV1 then
    begin
      BeginStep('v1');
      RemoveVersion1;
    end;
    BeginStep('files');
  end
  else if CurStep = ssPostInstall then
    FinishSteps;
end;

{ Files copied: the bar becomes a moving (marquee) bar until the helpers start. }
procedure CurInstallProgressChanged(CurProgress, MaxProgress: Integer);
begin
  if MaxProgress > 0 then
  begin
    FilesFrac := CurProgress;
    FilesFrac := FilesFrac / MaxProgress;
  end;
  if (MaxProgress > 0) and (CurProgress >= MaxProgress) and
     (WizardForm.ProgressGauge.Style <> npbstMarquee) then
  begin
    WizardForm.ProgressGauge.Style := npbstMarquee;
    WizardForm.FilenameLabel.Caption := 'Getting the helper tools ready...';
  end;
end;

{ SecureUxTheme was installed just now: it only works after a restart, so the last
  page offers one (Yes is preselected); the RunOnce entry opens the app afterwards. }
function NeedRestart: Boolean;
begin
  Result := WizardIsTaskSelected('secureux');
end;

{ Uninstall: an open Easy Theme Creator keeps its Python files locked (they would be
  left behind) and could fight the Undo, so it is closed first; at the end anything
  still running from the app folder is closed and the folder removed completely. }
procedure CloseAppProcesses;
var
  rc: Integer;
begin
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -ExecutionPolicy Bypass -Command "Get-Process | Where-Object { $_.Path -like ''' +
    ExpandConstant('{app}') + '\*'' } | Stop-Process -Force"', '', SW_HIDE, ewWaitUntilTerminated, rc);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    CloseAppProcesses
  else if CurUninstallStep = usPostUninstall then
  begin
    CloseAppProcesses;
    Sleep(1000);
    DelTree(ExpandConstant('{app}'), True, True, True);
  end;
end;

procedure DeinitializeSetup;
begin
  if ProgressTimer <> 0 then
    KillTimer(0, ProgressTimer);
  ProgressTimer := 0;
end;
