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
# A mod's version is in its DLL's name (<id>_<version>_<build>.dll). One of the three
# that Windhawk already has at that version or newer (installed or updated there by the
# user) keeps its files and registration; only the settings the app needs are added.
# -OnlyOurMod: an upgrade that runs this only because our own mod is outdated - the
# other three are left completely alone.
param([string]$ModDir, [string]$ThemeDir = "$env:ProgramData\EasyThemeCreator\redirect", [switch]$OnlyOurMod)
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
$our = 'easy-theme-creator-standard-colors'

# "1.10" is newer than "1.7"; versions that aren't dotted numbers only match themselves.
function Test-AtLeast([string]$have, [string]$want) {
    $h = $null; $w = $null
    if ([version]::TryParse($have, [ref]$h) -and [version]::TryParse($want, [ref]$w)) { return $h -ge $w }
    return $have -eq $want
}

# Our mod's process lists come from its own header (@include / @exclude lines), so they
# are exactly what Windhawk itself would register for it.
function Get-HeaderList([string]$file, [string]$tag) {
    $list = @()
    foreach ($line in [IO.File]::ReadAllLines($file)) {
        if ($line -match '^//\s*==/WindhawkMod==') { break }
        if ($line -match "^//\s*@$tag\s+(\S.*?)\s*$") { $list += $Matches[1] }
    }
    if ($list.Count -eq 0) { throw "No @$tag lines in $file" }
    return $list -join '|'
}

function Add-Mod([string]$id, [string]$include, [string]$exclude, [string]$custom) {
    # the DLL the installer brought: one per architecture the mod is built for, same name
    $dll = $null
    foreach ($arch in '32', '64') {
        $files = @(Get-ChildItem (Join-Path $ModDir $arch) -Filter "$id`_*.dll" -ErrorAction SilentlyContinue)
        if ($files.Count -gt 1) { throw "More than one $arch-bit DLL for $id" }
        if ($files.Count -eq 1) { $dll = $files[0].Name }
    }
    if (-not $dll) { Write-Host "No files for $id"; return $null }
    $build = $dll.Substring($id.Length + 1, $dll.Length - $id.Length - 5)      # "<version>_<build>"
    if ($build.LastIndexOf('_') -lt 1) { throw "Unexpected mod file name: $dll" }
    $version = $build.Substring(0, $build.LastIndexOf('_'))

    $key = "HKLM:\SOFTWARE\Windhawk\Engine\Mods\$id"
    $old = if (Test-Path $key) { Get-ItemProperty $key } else { $null }
    if ($id -ne $our -and $old -and $old.Version -and (Test-AtLeast $old.Version $version)) {
        Write-Host "$id $($old.Version) is already installed; keeping it."
        if (-not (Test-Path "$key\Settings")) { New-Item "$key\Settings" -Force | Out-Null }
        return "$key\Settings"
    }

    foreach ($arch in '32', '64') {
        $src = Join-Path $ModDir "$arch"
        if (-not (Test-Path (Join-Path $src $dll))) { continue }
        $dst = Join-Path $data "Engine\Mods\$arch"
        New-Item -ItemType Directory -Force $dst | Out-Null
        # Mod DLL names carry version + build id, so one already there is the same file -
        # and loaded in running programs (locked) on an upgrade: copy only new ones.
        if (-not (Test-Path (Join-Path $dst $dll))) { Copy-Item (Join-Path $src $dll) $dst }
        # an older version's DLL (still loaded in running programs until they restart: skip those)
        Get-ChildItem $dst -Filter "$id`_*.dll" | Where-Object { $_.Name -ne $dll } |
            ForEach-Object { Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue }
        foreach ($rt in 'libc++.whl', 'libunwind.whl', 'windhawk-mod-shim.dll') {
            if ((Test-Path (Join-Path $src $rt)) -and -not (Test-Path (Join-Path $dst $rt))) {
                Copy-Item (Join-Path $src $rt) $dst
            }
        }
    }
    $sources = Join-Path $data 'ModsSource'
    New-Item -ItemType Directory -Force $sources | Out-Null
    Copy-Item (Join-Path $ModDir "$id.wh.cpp") $sources -Force

    foreach ($k in $key, "$key\Settings") { if (-not (Test-Path $k)) { New-Item $k -Force | Out-Null } }
    $vals = @{ LibraryFileName = $dll; Include = $include; Exclude = $exclude; Architecture = ''; Version = $version }
    foreach ($n in $vals.Keys) { Set-ItemProperty $key -Name $n -Value $vals[$n] -Type String }
    # Our mod stays switched off if the user switched it off in Windhawk; the other three
    # are only (re)registered here because their task was ticked, so they are switched on.
    $disabled = 0
    if ($id -eq $our -and $old -and $null -ne $old.Disabled) { $disabled = $old.Disabled }
    Set-ItemProperty $key -Name Disabled -Value $disabled -Type DWord
    Set-ItemProperty $key -Name SettingsChangeTime -Value $now -Type DWord
    if ($custom) {
        Set-ItemProperty $key -Name IncludeCustom -Value $custom -Type String
        Set-ItemProperty $key -Name IncludeExcludeCustomOnly -Value 1 -Type DWord
    }
    return "$key\Settings"
}

# 1. Resource Redirect: keep existing settings, add our theme folder to "Theme paths" once.
$set = if ($OnlyOurMod) { $null } else { Add-Mod 'icon-resource-redirect' '*' '' 'explorer.exe' }
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
# "readable text" mod (starts with an empty list; the app's "Fix an app" button fills
# it). Users may write their settings.
$ours = Join-Path $ModDir "$our.wh.cpp"
$list = @()
if (-not $OnlyOurMod) {
    $list += , @('windows-11-taskbar-styler', 'explorer.exe', '')
    $list += , @('windows-11-file-explorer-styler', 'explorer.exe', '')
}
$list += , @($our, (Get-HeaderList $ours 'include'), (Get-HeaderList $ours 'exclude'))
foreach ($m in $list) {
    $set = Add-Mod $m[0] $m[1] $m[2] ''
    if (-not $set) { continue }
    $props = Get-ItemProperty $set
    if ($m[0] -eq $our) {
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
