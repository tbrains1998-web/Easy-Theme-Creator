# Fully automatic test inside Windows Sandbox (no clicks):
# v1 installed first -> v2 silent install (must remove v1) -> self-test (Apply, checks,
# screenshots, Undo) -> silent uninstall -> leftover check. Results in C:\sbx\results.
$res = 'C:\sbx\results'
New-Item -ItemType Directory -Force $res | Out-Null
Get-ChildItem $res | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
$report = Join-Path $res 'auto-report.txt'
function Say($t) { $t | Out-File $report -Append -Encoding utf8 }
function Check($name, $ok, $detail = '') {
    Say(("[{0}] {1}{2}" -f $(if ($ok) { 'OK  ' } else { 'FAIL' }), $name, $(if (-not $ok -and $detail) { "   -- $detail" } else { '' })))
}
Say "Started $(Get-Date)"
$app = "$env:ProgramFiles\Easy Theme Creator"
$v1Key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\EasyThemeCreator'

# 1. the old version, as a friend might already have it
Start-Process 'C:\sbxv1\Easy Theme Creator Setup.exe' -ArgumentList '/S' -Wait
Start-Sleep 3
Check 'v1 installed first (test setup)' (Test-Path $v1Key)

# 2. v2, default choices. /SILENT (not /VERYSILENT) still needs no clicks but shows the
# progress window - the moving bar and "Step x of 6" texts - so it can be watched, and
# it is photographed every 15 s (install-01.png ...) as proof.
# Windows Installer logs (MSI*.LOG in TEMP), to see where the two MSIs spend ~2 minutes each
New-Item 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Installer' -Force | Out-Null
Set-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Installer' -Name Logging -Value 'voicewarmupx'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type -Namespace Etc -Name Dpi -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
[Etc.Dpi]::SetProcessDPIAware() | Out-Null
function Photo($file) {
    try {
        $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
        $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($b.Left, $b.Top, 0, 0, $bmp.Size)
        $bmp.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $bmp.Dispose()
    } catch { Say "photo failed: $_" }
}
$p = Start-Process 'C:\sbxdist\Easy Theme Creator Setup.exe' -ArgumentList "/SILENT /SUPPRESSMSGBOXES /NORESTART /LOG=`"$res\install.log`"" -PassThru
$null = $p.Handle          # keep a handle, or ExitCode is empty once it has exited
for ($i = 1; -not $p.WaitForExit(15000) -and $i -le 40; $i++) { Photo ("$res\install-{0:D2}.png" -f $i) }
$p.WaitForExit()
Check 'v2 installer exit code 0' ($p.ExitCode -eq 0) $p.ExitCode
New-Item -ItemType Directory -Force "$res\msi-logs" | Out-Null
Get-ChildItem $env:TEMP, "$env:windir\Temp" -Filter 'MSI*.LOG' -ErrorAction SilentlyContinue | Copy-Item -Destination "$res\msi-logs" -ErrorAction SilentlyContinue
Check 'v1 removed by the v2 installer' (-not (Test-Path $v1Key))
Check 'v1 files gone' (-not (Test-Path "$env:LOCALAPPDATA\Programs\Easy Theme Creator"))
Check 'v2 app installed' (Test-Path "$app\app\easy_theme_creator.py")
Check 'Open-Shell installed' (Test-Path "$env:ProgramFiles\Open-Shell\StartMenu.exe")
Check 'Windhawk installed' (Test-Path "$env:ProgramFiles\Windhawk\windhawk.exe")
$sc = 'HKLM:\SOFTWARE\Windhawk\Engine\Mods\easy-theme-creator-standard-colors'
$scDll = if (Test-Path $sc) { (Get-ItemProperty $sc).LibraryFileName } else { '' }
Check 'standard-colours mod registered' ($scDll -and (Test-Path "$env:ProgramData\Windhawk\Engine\Mods\64\$scDll")) $scDll
if (Test-Path "$sc\Settings") { Check 'standard-colours mod settings writable by users' ((Get-Acl "$sc\Settings").Sddl -match '(0x2001b|CCDCSWRPRC);;;BU') }
$newVersion = (Get-ItemProperty $sc -ErrorAction SilentlyContinue).Version

# 2b. upgrade over an install whose own mod is older. Inno remembers the earlier
# install's tasks, where "Windhawk + mods" was hidden (ready) and so unticked: setup
# must still update our mod (2.3 first missed it on a real upgrade).
Set-ItemProperty $sc -Name Version -Value '1.0'
$p = Start-Process 'C:\sbxdist\Easy Theme Creator Setup.exe' -ArgumentList "/SILENT /SUPPRESSMSGBOXES /NORESTART /TASKS=`"desktopicon`" /LOG=`"$res\upgrade.log`"" -PassThru
$null = $p.Handle
$p.WaitForExit()
$after = Get-ItemProperty $sc -ErrorAction SilentlyContinue
Check 'upgrade without the Windhawk task updates our mod' ($p.ExitCode -eq 0 -and $after.Version -eq $newVersion -and
    (Test-Path "$env:ProgramData\Windhawk\Engine\Mods\64\$($after.LibraryFileName)")) "exit $($p.ExitCode), version $($after.Version), want $newVersion"
Start-Sleep 10   # let Windhawk load its mods into Explorer

# 3. the app itself: Apply, checks, screenshots, Undo
# (no -Wait: in PowerShell 5.1 it also waits for everything the process starts -
#  the Explorer / Control Panel windows, Open-Shell - and then never returns)
$t = Start-Process "$app\python\python.exe" -ArgumentList "-X utf8 `"C:\sbx\selftest.py`" `"$res`"" -WorkingDirectory "$app\app" -PassThru -RedirectStandardError "$res\selftest-stderr.txt"
for ($i = 0; $i -lt 900 -and -not $t.HasExited; $i++) { Start-Sleep 1 }
Check 'self-test finished within 15 minutes' $t.HasExited
if (-not $t.HasExited) { Stop-Process -Id $t.Id -Force -ErrorAction SilentlyContinue }   # or it fights the uninstall
Check 'self-test ran' (Test-Path "$res\selftest.txt")
if (Test-Path "$res\selftest.txt") { Get-Content "$res\selftest.txt" | Select-String '^\[|RESULT|CRASH' | % { Say $_.Line } }

# 4. uninstall silently (it runs Undo itself first)
Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "$app\*" } | % { Say ("running before uninstall: pid {0}  {1}" -f $_.ProcessId, $_.CommandLine) }
$un = Get-ChildItem $app -Filter 'unins*.exe' | Select-Object -First 1
if ($un) {
    Start-Process $un.FullName -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART'   # no -Wait, see step 3
    # it runs Undo first (Explorer restart, Open-Shell), then deletes the files from TEMP
    for ($i = 0; $i -lt 300 -and (Test-Path "$app\app"); $i++) { Start-Sleep 1 }
    Start-Sleep 5
}
Check 'uninstall removed the app' (-not (Test-Path "$app\app"))
if (Test-Path $app) { Say "left in ${app}:"; Get-ChildItem $app -Recurse -Force | Select-Object -First 30 | % { Say ("   " + $_.FullName) } }
# the self-test left the theme on, so the uninstaller's own Undo had to put the old look back
$adv = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' -ErrorAction SilentlyContinue
Check 'uninstall put the taskbar icons back (centered)' ($null -eq $adv.TaskbarAl) $adv.TaskbarAl
$os = Get-ItemProperty 'HKCU:\Software\OpenShell\StartMenu\Settings' -ErrorAction SilentlyContinue
Check 'uninstall put the Start menu back' ($null -eq $os.SkinW7 -and $null -eq $os.MenuStyle) "$($os.SkinW7) / $($os.MenuStyle)"
$tb = Get-ItemProperty 'HKLM:\SOFTWARE\Windhawk\Engine\Mods\windows-11-taskbar-styler\Settings' -ErrorAction SilentlyContinue
Check 'uninstall removed the taskbar styles' ($tb.'styleConstants[0]' -ne '// Easy Theme Creator')
$wp = (Get-ItemProperty 'HKCU:\Control Panel\Desktop' -ErrorAction SilentlyContinue).Wallpaper
Check 'uninstall put the wallpaper back' ($wp -and $wp -notlike '*Test Picture*') $wp
Check 'uninstall left no Undo snapshot (its Undo worked)' (-not (Test-Path "$env:LOCALAPPDATA\EasyThemeCreator\undo\state.json"))
Check 'uninstall removed the Start menu skin file' (-not (Test-Path "$env:ProgramFiles\Open-Shell\Skins\Easy Theme Armor.skin7"))
Check 'uninstall removed ProgramData files' (-not (Test-Path "$env:ProgramData\EasyThemeCreator"))
Check 'uninstall removed the shortcuts' (-not (Test-Path "$env:PUBLIC\Desktop\Easy Theme Creator.lnk") -and -not (Test-Path "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Easy Theme Creator.lnk"))
Check 'uninstall entry gone' (-not (Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | Where-Object DisplayName -eq 'Easy Theme Creator'))
foreach ($f in (Get-ChildItem "$env:ProgramData\Windhawk\Logs", "$env:LOCALAPPDATA\Windhawk" -Recurse -Include '*.log','*.txt' -ErrorAction SilentlyContinue)) { Copy-Item $f.FullName "$res\wh-$($f.Name)" -ErrorAction SilentlyContinue }
Say "Finished $(Get-Date)"
