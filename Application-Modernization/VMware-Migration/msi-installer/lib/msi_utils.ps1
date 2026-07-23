# lib/msi_utils.ps1 — Core MSI installation functions
# Shared library for the MSI Batch Installer project

# --- Check if running as Administrator ---
function Test-Administrator {
    $principal = [Security.Principal.WindowsPrincipal]::new(
        [Security.Principal.WindowsIdentity]::GetCurrent()
    )
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# --- Decode msiexec exit code into human-readable message ---
function Get-MsiExitMessage {
    param([int]$Code)
    switch ($Code) {
           0 { 'Success' }
        1602 { 'User cancelled' }
        1603 { 'Fatal error (check permissions / locked files)' }
        1604 { 'Installation suspended, incomplete' }
        1605 { 'Action only valid for installed products' }
        1606 { 'Feature ID not registered' }
        1607 { 'Component ID not registered' }
        1608 { 'Unknown property' }
        1609 { 'Handle in an invalid state' }
        1610 { 'Configuration data corrupt' }
        1611 { 'Product qualifier not present' }
        1612 { 'Installation source unavailable' }
        1613 { 'Installation version too old' }
        1614 { 'Product is not installed' }
        1615 { 'SQL query syntax invalid' }
        1616 { 'Record field does not exist' }
        1618 { 'Another installation is already running' }
        1619 { 'MSI file could not be opened (missing or corrupt)' }
        1620 { 'Invalid package type' }
        1621 { 'Installer service failed to start' }
        1622 { 'Error opening installation log file' }
        1625 { 'System policy prevents installation' }
        1638 { 'Another version of this product is already installed' }
        1639 { 'Invalid command-line argument' }
        1640 { 'Installation from a Terminal Server not permitted' }
        1641 { 'Installer service started, reboot required' }
        1642 { 'Upgrade not possible (version mismatch)' }
        3010 { 'Success - reboot required' }
        default { "Unknown error code: $Code" }
    }
}

# --- Determine if an exit code represents success ---
function Test-MsiSuccess {
    param([int]$Code)
    return ($Code -eq 0 -or $Code -eq 3010)
}

# --- Build msiexec argument string ---
function Build-MsiexecArgs {
    param(
        [string]$MsiPath,
        [string]$UiFlag,
        [string]$NoRebootFlag,
        [string]$LogPath,
        [string]$PropertiesStr
    )
    return "/i `"$MsiPath`" $UiFlag $NoRebootFlag /L*V `"$LogPath`"$PropertiesStr"
}

# --- Build UI flag from mode string ---
function Get-UiFlag {
    param([string]$UiMode)
    switch ($UiMode) {
        'silent' { '/qn' }
        'basic'  { '/qb' }
        'full'   { '' }
        default  { '/qn' }
    }
}

# --- Build properties string from hashtable ---
function Build-PropertiesString {
    param([hashtable]$Properties)
    if (-not $Properties) { return '' }
    $str = ''
    foreach ($key in $Properties.Keys) {
        $val = $Properties[$key]
        $str += " $key=`"$val`""
    }
    return $str
}

# --- Install a single MSI package ---
function Install-MsiPackage {
    param(
        [string]$MsiPath,
        [string]$UiMode = 'silent',
        [switch]$NoReboot = $true,
        [string]$LogPath,
        [hashtable]$Properties
    )

    $uiFlag       = Get-UiFlag -UiMode $UiMode
    $noRebootFlag = if ($NoReboot) { '/norestart' } else { '' }
    $propStr      = Build-PropertiesString -Properties $Properties
    $argList      = Build-MsiexecArgs -MsiPath $MsiPath -UiFlag $uiFlag -NoRebootFlag $noRebootFlag -LogPath $LogPath -PropertiesStr $propStr

    $proc = Start-Process -FilePath 'msiexec.exe' -ArgumentList $argList -Wait -PassThru -NoNewWindow

    return [pscustomobject]@{
        ExitCode  = $proc.ExitCode
        Message   = Get-MsiExitMessage -Code $proc.ExitCode
        Success   = Test-MsiSuccess -Code $proc.ExitCode
    }
}

# --- Generate timestamped log file path ---
function Get-TimestampedLogPath {
    param(
        [string]$LogDir,
        [string]$BaseName
    )
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $safeName  = $BaseName -replace '[^\w\-]', '_'
    return Join-Path $LogDir "${safeName}_${timestamp}.log"
}

# --- Verify a product is installed via registry ---
function Test-ProductInstalled {
    param([string]$ProductName)

    $keys = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )

    foreach ($key in $keys) {
        $found = Get-ItemProperty $key -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -match $ProductName }
        if ($found) { return $found }
    }
    return $null
}
