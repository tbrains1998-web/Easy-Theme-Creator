# Run by the Easy Theme Creator installer (elevated) after Windhawk is installed.
# Adds three prebuilt Windhawk mods (all GPL-3.0, by m417z; their source code is
# included next to them as <id>.wh.cpp):
#   icon-resource-redirect           dark Control Panel side pane (Explorer only)
#   windows-11-taskbar-styler        metal taskbar + Alien Start button
#   windows-11-file-explorer-styler  armor plates on Explorer's bars
# plus our own mod (MIT, source next to it):
#   easy-theme-creator-standard-colors  readable dialog text everywhere + Windows' normal
#                                       colours for programs the user lists
# Then lets normal users write those mods' settings (so the app can change them
# without an admin prompt) and restarts Windhawk so it loads them.
param([string]$ModDir, [string]$ThemeDir = "$env:ProgramData\EasyThemeCreator\redirect")
$ErrorActionPreference = 'Stop'
trap {      # setup runs this hidden and only sees an exit code: keep the reason
    "$(Get-Date -Format s)  line $($_.InvocationInfo.ScriptLineNumber): $_" |
        Out-File -Append -Encoding utf8 (Join-Path $env:ProgramData 'EasyThemeCreator\setup-windhawk-mod.log')
    exit 1
}
$exe = Join-Path $env:ProgramFiles 'Windhawk\windhawk.exe'
if (-not (Test-Path $exe)) { Write-Output 'Windhawk is not installed; skipping the mods.'; exit 0 }
$data = Join-Path $env:ProgramData 'Windhawk'
$now = [int][double]::Parse((Get-Date -UFormat %s))

function Add-Mod([string]$id, [string]$version, [string]$include, [string]$custom) {
    $found = $false
    foreach ($arch in '32', '64') {
        $src = Join-Path $ModDir "$arch"
        $files = @(Get-ChildItem $src -Filter "$id`_*.dll" -ErrorAction SilentlyContinue)
        if ($files.Count -eq 0) { continue }
        $dst = Join-Path $data "Engine\Mods\$arch"
        New-Item -ItemType Directory -Force $dst | Out-Null
        # Mod DLL names carry version + build id, so one already there is the same file -
        # and loaded in running programs (locked) on an upgrade: copy only new ones.
        foreach ($f in $files) {
            if (-not (Test-Path (Join-Path $dst $f.Name))) { Copy-Item $f.FullName $dst }
        }
        # an older version's DLL (still loaded in running programs until they restart: skip those)
        Get-ChildItem $dst -Filter "$id`_*.dll" | Where-Object { $_.Name -ne $files[0].Name } |
            ForEach-Object { Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue }
        foreach ($rt in 'libc++.whl', 'libunwind.whl', 'windhawk-mod-shim.dll') {
            if ((Test-Path (Join-Path $src $rt)) -and -not (Test-Path (Join-Path $dst $rt))) {
                Copy-Item (Join-Path $src $rt) $dst
            }
        }
        $dll = $files[0].Name
        $found = $true
    }
    if (-not $found) { Write-Host "No files for $id"; return $null }
    $sources = Join-Path $data 'ModsSource'
    New-Item -ItemType Directory -Force $sources | Out-Null
    Copy-Item (Join-Path $ModDir "$id.wh.cpp") $sources -Force

    $key = "HKLM:\SOFTWARE\Windhawk\Engine\Mods\$id"
    foreach ($k in $key, "$key\Settings") { if (-not (Test-Path $k)) { New-Item $k -Force | Out-Null } }
    $vals = @{ LibraryFileName = $dll; Include = $include; Exclude = ''; Architecture = ''; Version = $version }
    foreach ($n in $vals.Keys) { Set-ItemProperty $key -Name $n -Value $vals[$n] -Type String }
    Set-ItemProperty $key -Name Disabled -Value 0 -Type DWord
    Set-ItemProperty $key -Name SettingsChangeTime -Value $now -Type DWord
    if ($custom) {
        Set-ItemProperty $key -Name IncludeCustom -Value $custom -Type String
        Set-ItemProperty $key -Name IncludeExcludeCustomOnly -Value 1 -Type DWord
    }
    return "$key\Settings"
}

# 1. Resource Redirect: keep existing settings, add our theme folder to "Theme paths" once.
$set = Add-Mod 'icon-resource-redirect' '1.3' '*' 'explorer.exe'
if ($set) {
    $props = Get-ItemProperty $set
    foreach ($n in 'iconTheme', 'themeFolder', 'redirectionResourcePaths[0].original', 'redirectionResourcePaths[0].redirect') {
        if ($null -eq $props.$n) { Set-ItemProperty $set -Name $n -Value '' -Type String }
    }
    if ($null -eq $props.disableThumbnails) { Set-ItemProperty $set -Name disableThumbnails -Value 0 -Type DWord }
    # "Redirect all loaded resources": Explorer loads its folder layouts (UIFILE, used for
    # the bottom details pane) with plain FindResource calls, which the mod only redirects
    # with this on. Resources our file doesn't have fall back to Windows' own.
    Set-ItemProperty $set -Name allResourceRedirect -Value 1 -Type DWord
    $i = 0
    while ($true) {
        $v = $props."themePaths[$i]"
        if ($null -eq $v -or $v -eq '' -or $v.TrimEnd('\') -ieq $ThemeDir.TrimEnd('\')) { break }
        $i++
    }
    Set-ItemProperty $set -Name "themePaths[$i]" -Value $ThemeDir -Type String
}

# 2-4. The stylers (start with no styles; the app writes them on Apply) and our own
# "standard colours for chosen apps" mod (starts with an empty list; the app's "Fix an
# app" button fills it). Users may write their settings.
foreach ($m in @(@('windows-11-taskbar-styler', '1.10', 'explorer.exe'), @('windows-11-file-explorer-styler', '1.7', 'explorer.exe'),
                 @('easy-theme-creator-standard-colors', '1.2', '*'))) {
    $set = Add-Mod $m[0] $m[1] $m[2] ''
    if (-not $set) { continue }
    $props = Get-ItemProperty $set
    if ($m[0] -eq 'easy-theme-creator-standard-colors') {
        Set-ItemProperty (Split-Path $set) -Name Exclude -Value 'windhawk.exe' -Type String
        if ($null -eq $props.'apps[0]') { Set-ItemProperty $set -Name 'apps[0]' -Value '' -Type String }
    } elseif ($null -eq $props.theme) {
        Set-ItemProperty $set -Name theme -Value '' -Type String
        Set-ItemProperty $set -Name 'controlStyles[0].target' -Value '' -Type String
        Set-ItemProperty $set -Name 'controlStyles[0].styles[0]' -Value '' -Type String
    }
    # Windhawk's key has a non-canonical permission list, so AddAccessRule refuses it;
    # add "Users: set + read values" (0x2001b) to the SDDL text instead.
    $acl = Get-Acl $set
    if ($acl.Sddl -notmatch '\(A;;(0x2001b|CCDCSWRPRC);;;BU\)') {     # Windows rewrites the mask
        $acl.SetSecurityDescriptorSddlForm(($acl.Sddl -replace '(D:[A-Z]*)', '$1(A;;0x2001b;;;BU)'))
        Set-Acl $set $acl
    }
}

try { Restart-Service Windhawk -ErrorAction Stop } catch { Start-Process $exe -ArgumentList '-restart', '-tray-only' }
Write-Output 'Windhawk mods ready.'
