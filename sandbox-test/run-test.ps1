# Runs inside Windows Sandbox: starts the installer (you click through it like a
# friend would), then writes a report of what ended up installed to
# results\interactive\report.txt (UTF-8). The automatic test's results stay untouched.
$res = 'C:\sbx\results\interactive'
New-Item -ItemType Directory -Force $res | Out-Null
Remove-Item "$res\*" -Force -ErrorAction SilentlyContinue
$log = Join-Path $res 'install.log'
$report = Join-Path $res 'report.txt'
function Say($t) { $t | Out-File $report -Append -Encoding utf8 }
Say "Started $(Get-Date)"

# no -Wait: PowerShell 5.1 would also wait for everything Setup starts (the app from its
# last page), so the report would only appear once the app is closed again
$app = "$env:ProgramFiles\Easy Theme Creator"
if (Test-Path "$app\app\easy_theme_creator.py") {
    Say "Already installed (this is the sign-in after the restart): skipping Setup"
} else {
    $p = Start-Process 'C:\sbxdist\Easy Theme Creator Setup.exe' -ArgumentList "/LOG=`"$log`"" -PassThru
    $null = $p.Handle          # keep a handle, or ExitCode is empty once it has exited
    $p.WaitForExit()
    Say "Installer exit code: $($p.ExitCode)"
}

function Check($name, $ok) { Say ("[{0}] {1}" -f $(if ($ok) { 'OK  ' } else { 'FAIL' }), $name) }
$app = "$env:ProgramFiles\Easy Theme Creator"
Check 'App files' (Test-Path "$app\app\easy_theme_creator.py")
Check 'Bundled Python' (Test-Path "$app\python\pythonw.exe")
Check 'Start menu shortcut' (Test-Path "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Easy Theme Creator.lnk")
Check 'ProgramData folder writable by users' ((Get-Acl "$env:ProgramData\EasyThemeCreator").Access | Where-Object { $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq 'S-1-5-32-545' -and $_.FileSystemRights -match 'Modify|FullControl' })
Check 'SecureUxTheme' (Test-Path "$env:windir\System32\SecureUxTheme4.dll")
Check 'Windhawk' (Test-Path "$env:ProgramFiles\Windhawk\windhawk.exe")
$k = 'HKLM:\SOFTWARE\Windhawk\Engine\Mods\icon-resource-redirect'
Check 'Resource Redirect mod registered' (Test-Path $k)
Check 'Mod DLL present' (Test-Path "$env:ProgramData\Windhawk\Engine\Mods\64\icon-resource-redirect*.dll")
if (Test-Path $k) { Say (Get-ItemProperty $k, "$k\Settings" | Out-String) }
foreach ($m in 'windows-11-taskbar-styler', 'windows-11-file-explorer-styler') {
    $mk = "HKLM:\SOFTWARE\Windhawk\Engine\Mods\$m"
    Check "$m registered" (Test-Path $mk)
    if (Test-Path "$mk\Settings") {
        Check "$m settings writable by users" ((Get-Acl "$mk\Settings").Sddl -match '(0x2001b|CCDCSWRPRC);;;BU')
    }
}
Check 'Open-Shell Start menu' (Test-Path "$env:ProgramFiles\Open-Shell\StartMenu.exe")
Check 'Open-Shell Classic Explorer NOT installed' (-not (Test-Path "$env:ProgramFiles\Open-Shell\ClassicExplorer64.dll"))
$skin = "$env:ProgramFiles\Open-Shell\Skins\Easy Theme Armor.skin7"
Check 'Armor skin file' (Test-Path $skin)
if (Test-Path $skin) { Check 'Armor skin writable by users' (((icacls $skin) -join ' ') -match 'Users:\(M\)|Gebruikers:\(M\)|S-1-5-32-545:\(M\)') ; Say ((icacls $skin) -join "`n") }
Check 'Windhawk service running' ((Get-Service Windhawk -ErrorAction SilentlyContinue).Status -eq 'Running')

# Only report what Setup left: the app is never started from here (the tester decides
# on Setup's last page; after SecureUxTheme the app opens by itself after the restart).
Start-Sleep 12
$open = @(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like '*launch.pyw*' }).Count
Say "App windows open now: $open"
$ro = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce' -ErrorAction SilentlyContinue).EasyThemeCreator
Say "Opens after the restart (RunOnce): $ro"
$err = "$env:LOCALAPPDATA\EasyThemeCreator\error.txt"
if (Test-Path $err) { Say ("App error:`r`n" + (Get-Content $err -Raw)) }
Say "Finished $(Get-Date)"

# Screenshots on request from the host: drop a file C:\sbx\shoot\<name>.txt (the folder is
# shared) and <name>.png appears in results\interactive\shots. Runs for up to 2 hours.
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type -Namespace Etc -Name Dpi -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
[Etc.Dpi]::SetProcessDPIAware() | Out-Null
$shoot = 'C:\sbx\shoot'; $shots = "$res\shots"
New-Item -ItemType Directory -Force $shoot, $shots | Out-Null
Remove-Item "$shoot\*" -Force -ErrorAction SilentlyContinue
$end = (Get-Date).AddHours(2)
while ((Get-Date) -lt $end) {
    foreach ($t in Get-ChildItem $shoot -Filter '*.txt' -ErrorAction SilentlyContinue) {
        Start-Sleep -Milliseconds 300
        try {
            $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
            $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
            $g = [System.Drawing.Graphics]::FromImage($bmp)
            $g.CopyFromScreen($b.Left, $b.Top, 0, 0, $bmp.Size)
            $bmp.Save("$shots\$($t.BaseName).png", [System.Drawing.Imaging.ImageFormat]::Png)
            $g.Dispose(); $bmp.Dispose()
        } catch { Say "shot $($t.BaseName) failed: $_" }
        Remove-Item $t.FullName -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 500
}
