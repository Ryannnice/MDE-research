#Requires -RunAsAdministrator
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$accountName = "piper_remote"
$projectRoot = "C:\Desktop\PIPER"
$stateRoot = Join-Path $env:ProgramData "PiperRemote"
$sshRoot = Join-Path $env:ProgramData "ssh"
$sshdConfig = Join-Path $sshRoot "sshd_config"
$systemOpenSshRoot = Join-Path $env:WINDIR "System32\OpenSSH"
$programOpenSshRoot = Join-Path $env:ProgramFiles "OpenSSH"
$offlineOpenSshArchive = Join-Path $PSScriptRoot "OpenSSH-Win64.zip"
$offlineOpenSshSha256 = "23f50f3458c4c5d0b12217c6a5ddfde0137210a30fa870e98b29827f7b43aba5"
$powerShellExe = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
$taskName = "PIPER Remote Tunnel"
$managedBegin = "# BEGIN PIPER_REMOTE MANAGED BLOCK"
$managedEnd = "# END PIPER_REMOTE MANAGED BLOCK"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path $projectRoot)) {
    throw "Expected project directory does not exist: $projectRoot"
}

$existingSshdService = Get-Service -Name sshd -ErrorAction SilentlyContinue
$openSshRoot = $null
if ($null -ne $existingSshdService -and $existingSshdService.Status -eq "Running") {
    $servicePathName = (Get-CimInstance Win32_Service -Filter "Name='sshd'").PathName
    $serviceExecutable = $null
    if ($servicePathName -match '^\s*"([^"]+)"') {
        $serviceExecutable = $Matches[1]
    }
    elseif ($servicePathName -match '^\s*(.+?sshd\.exe)') {
        $serviceExecutable = $Matches[1]
    }
    if ($null -ne $serviceExecutable -and (Test-Path $serviceExecutable)) {
        $openSshRoot = Split-Path $serviceExecutable
    }
}
if ($null -eq $openSshRoot) {
    if (-not (Test-Path $offlineOpenSshArchive)) {
        throw "Bundled OpenSSH archive is missing: $offlineOpenSshArchive"
    }
    $archiveSha256 = (Get-FileHash -LiteralPath $offlineOpenSshArchive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($archiveSha256 -ne $offlineOpenSshSha256) {
        throw "Bundled OpenSSH archive failed SHA-256 verification."
    }

    Write-Host "Installing bundled Microsoft Win32-OpenSSH..."
    $temporaryRoot = Join-Path $env:TEMP ("PiperOpenSSH-" + [Guid]::NewGuid().ToString("N"))
    try {
        Expand-Archive -LiteralPath $offlineOpenSshArchive -DestinationPath $temporaryRoot
        $offlineSource = Join-Path $temporaryRoot "OpenSSH-Win64"
        if (-not (Test-Path (Join-Path $offlineSource "install-sshd.ps1"))) {
            throw "Bundled OpenSSH archive has an unexpected layout."
        }
        New-Item -ItemType Directory -Path $programOpenSshRoot -Force | Out-Null
        Copy-Item -Path (Join-Path $offlineSource "*") -Destination $programOpenSshRoot -Recurse -Force
        Get-ChildItem $programOpenSshRoot -Recurse -File | Unblock-File
        $installSshdScript = Join-Path $programOpenSshRoot "install-sshd.ps1"
        & $powerShellExe `
            -NoLogo `
            -NoProfile `
            -NonInteractive `
            -ExecutionPolicy Bypass `
            -File $installSshdScript
        if ($LASTEXITCODE -ne 0) {
            throw "Bundled OpenSSH service installation failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        if (Test-Path $temporaryRoot) {
            Remove-Item $temporaryRoot -Recurse -Force
        }
    }
    $openSshRoot = $programOpenSshRoot
}

$sshdExe = Join-Path $openSshRoot "sshd.exe"
$sshdDefaultConfig = Join-Path $openSshRoot "sshd_config_default"
$sshKeygenExe = Join-Path $openSshRoot "ssh-keygen.exe"
$sshExe = @(
    (Join-Path $systemOpenSshRoot "ssh.exe"),
    (Join-Path $openSshRoot "ssh.exe")
) | Where-Object { Test-Path $_ } | Select-Object -First 1
foreach ($requiredExecutable in @($sshdExe, $sshKeygenExe, $sshExe)) {
    if (-not (Test-Path $requiredExecutable)) {
        throw "Required OpenSSH executable is missing: $requiredExecutable"
    }
}

New-Item -ItemType Directory -Path $sshRoot -Force | Out-Null
if (-not (Test-Path $sshdConfig)) {
    if (-not (Test-Path $sshdDefaultConfig)) {
        throw "OpenSSH default configuration is missing: $sshdDefaultConfig"
    }
    Copy-Item $sshdDefaultConfig $sshdConfig
}
$hostKeyArguments = @("-A")
Invoke-Checked -FilePath $sshKeygenExe -Arguments $hostKeyArguments

New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null

$account = Get-LocalUser -Name $accountName -ErrorAction SilentlyContinue
if ($null -eq $account) {
    $passwordBytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($passwordBytes)
    }
    finally {
        $rng.Dispose()
    }
    $randomPassword = [Convert]::ToBase64String($passwordBytes) + "!aA1"
    $securePassword = ConvertTo-SecureString $randomPassword -AsPlainText -Force
    $account = New-LocalUser `
        -Name $accountName `
        -Password $securePassword `
        -AccountNeverExpires `
        -PasswordNeverExpires `
        -UserMayNotChangePassword `
        -Description "PIPER robot and RealSense remote automation"
}
elseif (-not $account.Enabled) {
    Enable-LocalUser -Name $accountName
}

$administrators = Get-LocalGroup -SID "S-1-5-32-544"
$isAdministrator = Get-LocalGroupMember -Group $administrators.Name -ErrorAction SilentlyContinue |
    Where-Object { $_.SID -eq $account.SID }
if ($null -eq $isAdministrator) {
    Add-LocalGroupMember -Group $administrators.Name -Member $accountName
}

$operatorKeySource = Join-Path $PSScriptRoot "operator_authorized_keys"
$operatorKeyTarget = Join-Path $stateRoot "operator_authorized_keys"
$tunnelKeySource = Join-Path $PSScriptRoot "tunnel_ed25519"
$tunnelKeyTarget = Join-Path $stateRoot "tunnel_ed25519"
$knownHostsSource = Join-Path $PSScriptRoot "known_hosts"
$knownHostsTarget = Join-Path $stateRoot "known_hosts"
$tunnelScriptSource = Join-Path $PSScriptRoot "piper_tunnel.ps1"
$tunnelScriptTarget = Join-Path $stateRoot "piper_tunnel.ps1"

foreach ($source in @(
    $operatorKeySource,
    $tunnelKeySource,
    $knownHostsSource,
    $tunnelScriptSource
)) {
    if (-not (Test-Path $source)) {
        throw "Bootstrap asset is missing: $source"
    }
}

Copy-Item $operatorKeySource $operatorKeyTarget -Force
Copy-Item $tunnelKeySource $tunnelKeyTarget -Force
Copy-Item $knownHostsSource $knownHostsTarget -Force
Copy-Item $tunnelScriptSource $tunnelScriptTarget -Force

$systemSid = "*S-1-5-18"
$administratorsSid = "*S-1-5-32-544"
Invoke-Checked icacls.exe $stateRoot /inheritance:r
Invoke-Checked icacls.exe $stateRoot /grant:r `
    "${systemSid}:(OI)(CI)F" `
    "${administratorsSid}:(OI)(CI)F"
foreach ($protectedFile in @(
    $operatorKeyTarget,
    $tunnelKeyTarget,
    $knownHostsTarget,
    $tunnelScriptTarget
)) {
    Invoke-Checked icacls.exe $protectedFile /inheritance:r
    Invoke-Checked icacls.exe $protectedFile /grant:r `
        "${systemSid}:F" `
        "${administratorsSid}:F"
}

Invoke-Checked icacls.exe $projectRoot /grant `
    "*$($account.SID):(OI)(CI)F"

$pythonRuntime = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312"
if (Test-Path $pythonRuntime) {
    Invoke-Checked icacls.exe $pythonRuntime /grant `
        "*$($account.SID):(OI)(CI)RX"
}

$originalLines = @(Get-Content $sshdConfig)
$sshdConfigBackup = Join-Path $stateRoot "sshd_config.before-piper-remote"
Copy-Item $sshdConfig $sshdConfigBackup -Force
$cleanLines = New-Object System.Collections.Generic.List[string]
$insideManagedBlock = $false
foreach ($line in $originalLines) {
    if ($line -eq $managedBegin) {
        $insideManagedBlock = $true
        continue
    }
    if ($line -eq $managedEnd) {
        $insideManagedBlock = $false
        continue
    }
    if (-not $insideManagedBlock) {
        $cleanLines.Add($line)
    }
}

$activeListenAddresses = @(
    $cleanLines |
        Where-Object { $_ -match '^\s*ListenAddress\s+' } |
        ForEach-Object { ($_ -split '\s+', 2)[1].Trim() }
)
if ($activeListenAddresses.Count -gt 0 -and
    @($activeListenAddresses | Where-Object { $_ -ne "127.0.0.1" }).Count -gt 0) {
    throw "Existing sshd ListenAddress is not loopback-only: $activeListenAddresses"
}

$firstMatch = -1
for ($index = 0; $index -lt $cleanLines.Count; $index++) {
    if ($cleanLines[$index] -match '^\s*Match\s+') {
        $firstMatch = $index
        break
    }
}
if ($firstMatch -lt 0) {
    $firstMatch = $cleanLines.Count
}

$prefix = @()
if ($firstMatch -gt 0) {
    $prefix = @($cleanLines.GetRange(0, $firstMatch))
}
$suffix = @()
if ($firstMatch -lt $cleanLines.Count) {
    $suffix = @($cleanLines.GetRange($firstMatch, $cleanLines.Count - $firstMatch))
}

if ($activeListenAddresses.Count -eq 0) {
    $prefix += "ListenAddress 127.0.0.1"
}
$managedBlock = @(
    $managedBegin,
    "Match User $accountName",
    "    AuthorizedKeysFile C:/ProgramData/PiperRemote/operator_authorized_keys",
    "    AuthenticationMethods publickey",
    "    PubkeyAuthentication yes",
    "    PasswordAuthentication no",
    "    KbdInteractiveAuthentication no",
    "    AllowTcpForwarding no",
    "    X11Forwarding no",
    "Match All",
    $managedEnd
)
try {
    Set-Content -Path $sshdConfig -Value @($prefix + $managedBlock + $suffix) -Encoding ascii

    $sshdValidationArguments = @("-t", "-f", $sshdConfig)
    Invoke-Checked -FilePath $sshdExe -Arguments $sshdValidationArguments
}
catch {
    Copy-Item $sshdConfigBackup $sshdConfig -Force
    throw
}

Set-Service -Name sshd -StartupType Automatic
$sshdService = Get-Service -Name sshd
if ($sshdService.Status -eq "Running") {
    Restart-Service -Name sshd -Force
}
else {
    Start-Service -Name sshd
}

$taskAction = New-ScheduledTaskAction `
    -Execute $powerShellExe `
    -Argument "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$tunnelScriptTarget`""
$taskTrigger = New-ScheduledTaskTrigger -AtStartup
$taskSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $taskAction `
    -Trigger $taskTrigger `
    -Settings $taskSettings `
    -User "SYSTEM" `
    -RunLevel Highest `
    -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Start-Sleep -Seconds 3
$service = Get-Service -Name sshd
$task = Get-ScheduledTask -TaskName $taskName
$listener = Get-NetTCPConnection `
    -LocalAddress "127.0.0.1" `
    -LocalPort 22 `
    -State Listen `
    -ErrorAction SilentlyContinue
if ($service.Status -ne "Running") {
    throw "OpenSSH server is not running."
}
if ($null -eq $listener) {
    throw "OpenSSH server is not listening on 127.0.0.1:22."
}
if ($task.State -ne "Running") {
    throw "Persistent reverse-tunnel task is not running."
}

$resultJson = [ordered]@{
    setup = "complete"
    account = $accountName
    account_is_local_administrator = $true
    project_root = $projectRoot
    openssh_server_executable = $sshdExe
    openssh_server_version = (Get-Item $sshdExe).VersionInfo.FileVersion
    sshd_status = $service.Status.ToString()
    sshd_loopback_listener = ($null -ne $listener)
    tunnel_task_state = $task.State.ToString()
    server_reverse_port = 22022
} | ConvertTo-Json
Set-Content -Path (Join-Path $stateRoot "install-result.json") -Value $resultJson -Encoding ascii
$resultJson
