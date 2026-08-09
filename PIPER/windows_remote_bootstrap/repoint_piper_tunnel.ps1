[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ServerHost,

    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 65535)]
    [int]$ServerPort,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedHostKeySHA256
)

$ErrorActionPreference = "Stop"
$stateRoot = Join-Path $env:ProgramData "PiperRemote"
$tunnelScript = Join-Path $stateRoot "piper_tunnel.ps1"
$knownHosts = Join-Path $stateRoot "known_hosts"
$taskName = "PIPER Remote Tunnel"

$principal = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated PowerShell."
}

foreach ($path in @($tunnelScript, $knownHosts)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required installed file is missing: $path"
    }
}
if ($ExpectedHostKeySHA256 -notmatch '^SHA256:[A-Za-z0-9+/]+$') {
    throw "ExpectedHostKeySHA256 is not a valid SHA256 SSH fingerprint."
}

$sshKeyscan = @(
    (Join-Path $env:ProgramFiles "OpenSSH\ssh-keyscan.exe"),
    (Join-Path $env:WINDIR "System32\OpenSSH\ssh-keyscan.exe")
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$sshKeygen = @(
    (Join-Path $env:ProgramFiles "OpenSSH\ssh-keygen.exe"),
    (Join-Path $env:WINDIR "System32\OpenSSH\ssh-keygen.exe")
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if ($null -eq $sshKeyscan -or $null -eq $sshKeygen) {
    throw "OpenSSH ssh-keyscan.exe or ssh-keygen.exe is unavailable."
}

$temporaryKnownHosts = Join-Path $env:TEMP (
    "piper-known-hosts-" + [Guid]::NewGuid().ToString("N")
)
try {
    $scan = @(& $sshKeyscan -p $ServerPort -t ed25519 $ServerHost 2>$null)
    if ($LASTEXITCODE -ne 0 -or $scan.Count -lt 1) {
        throw "Could not read the new server ED25519 host key."
    }
    Set-Content -LiteralPath $temporaryKnownHosts -Value $scan -Encoding ASCII

    $fingerprintOutput = & $sshKeygen -lf $temporaryKnownHosts -E sha256
    if ($LASTEXITCODE -ne 0 -or $fingerprintOutput -notmatch [regex]::Escape($ExpectedHostKeySHA256)) {
        throw "Server host-key fingerprint mismatch. Refusing to update the tunnel."
    }

    $lines = @(Get-Content -LiteralPath $tunnelScript)
    $portLines = @(0..($lines.Count - 1) | Where-Object {
        $lines[$_] -match '^\s*-p\s+\d+\s+`\s*$'
    })
    $hostLines = @(0..($lines.Count - 1) | Where-Object {
        $lines[$_] -match '^\s*"root@[^\"]+"\s+2>>\s+\$logPath\s*$'
    })
    if ($portLines.Count -ne 1 -or $hostLines.Count -ne 1) {
        throw "The installed tunnel script has an unexpected format; no changes were made."
    }

    $portIndent = [regex]::Match($lines[$portLines[0]], '^(\s*)').Groups[1].Value
    $hostIndent = [regex]::Match($lines[$hostLines[0]], '^(\s*)').Groups[1].Value
    $lines[$portLines[0]] = $portIndent + '-p ' + $ServerPort.ToString() + ' `'
    $lines[$hostLines[0]] = $hostIndent + '"root@' + $ServerHost + '" 2>> $logPath'

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item -LiteralPath $tunnelScript -Destination "$tunnelScript.$stamp.bak" -Force
    Copy-Item -LiteralPath $knownHosts -Destination "$knownHosts.$stamp.bak" -Force

    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Set-Content -LiteralPath $tunnelScript -Value $lines -Encoding ASCII
    Set-Content -LiteralPath $knownHosts -Value $scan -Encoding ASCII
    Start-ScheduledTask -TaskName $taskName
    Start-Sleep -Seconds 5

    $task = Get-ScheduledTask -TaskName $taskName
    if ($task.State -ne "Running") {
        throw "The tunnel task did not remain running after the update."
    }
    Write-Host "PIPER tunnel endpoint updated to ${ServerHost}:$ServerPort."
    Write-Host "Verified host key: $ExpectedHostKeySHA256"
    Write-Host "Task state: $($task.State)"
}
finally {
    if (Test-Path -LiteralPath $temporaryKnownHosts) {
        Remove-Item -LiteralPath $temporaryKnownHosts -Force
    }
}
