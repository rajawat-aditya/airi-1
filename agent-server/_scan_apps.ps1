$ErrorActionPreference = 'SilentlyContinue'
$results = [System.Collections.Generic.List[hashtable]]::new()
$seen    = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

function Add-App($name, $exe, $hint) {
    if (-not $exe) { return }
    $exe = $exe.Trim('"').Trim()
    if (-not $exe.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) { return }
    if (-not (Test-Path $exe -PathType Leaf)) { return }
    if (-not $seen.Add($exe)) { return }
    if (-not $hint) { $hint = [System.IO.Path]::GetFileNameWithoutExtension($exe) }
    if (-not $name) { $name = $hint }
    $results.Add(@{ name = $name.Trim(); exe = $exe; title_hint = $hint.Trim() })
}

# 1. Start Menu .lnk shortcuts
$shell = New-Object -ComObject WScript.Shell
@(
    [System.Environment]::GetFolderPath('StartMenu'),
    [System.Environment]::GetFolderPath('CommonStartMenu')
) | ForEach-Object {
    Get-ChildItem -Path $_ -Recurse -Filter '*.lnk' -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $lnk    = $shell.CreateShortcut($_.FullName)
            $target = $lnk.TargetPath
            $name   = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
            Add-App $name $target ''
        } catch {}
    }
}

# 2. Registry Uninstall keys (HKLM 64-bit, 32-bit, HKCU)
$regPaths = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
foreach ($rp in $regPaths) {
    Get-ItemProperty $rp -ErrorAction SilentlyContinue | ForEach-Object {
        $name = $_.DisplayName
        if (-not $name) { return }
        $icon = ($_.DisplayIcon -split ',')[0].Trim().Trim('"')
        if ($icon -and $icon.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
            Add-App $name $icon ''
            return
        }
        $loc = $_.InstallLocation
        if ($loc -and (Test-Path $loc -PathType Container)) {
            $stem = ($name -replace '[^a-zA-Z0-9]', '').ToLower()
            Get-ChildItem -Path $loc -Filter '*.exe' -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -notmatch 'uninstall|setup|update|helper|crash|redist' } |
                Sort-Object { [Math]::Abs($_.BaseName.ToLower().Length - $stem.Length) } |
                Select-Object -First 1 | ForEach-Object { Add-App $name $_.FullName '' }
        }
    }
}

# 3. Get-StartApps
Get-StartApps -ErrorAction SilentlyContinue | ForEach-Object {
    $appId = $_.AppID
    if ($appId -and $appId.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
        Add-App $_.Name $appId ''
    }
}

# 4. Common install directory scan
$scanDirs = @(
    $env:ProgramFiles,
    ${env:ProgramFiles(x86)},
    "$env:LOCALAPPDATA\Programs"
) | Where-Object { $_ -and (Test-Path $_) }
foreach ($dir in $scanDirs) {
    Get-ChildItem -Path $dir -Recurse -Filter '*.exe' -Depth 3 -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch 'uninstall|setup|update|helper|crash|redist|vcredist|dotnet' } |
        ForEach-Object {
            $name = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
            Add-App $name $_.FullName ''
        }
}

$results | ConvertTo-Json -Depth 2 -Compress