$ErrorActionPreference = "Continue"
$stateRoot = Join-Path $env:ProgramData "PiperRemote"
$sshExe = @(
    (Join-Path $env:WINDIR "System32\OpenSSH\ssh.exe"),
    (Join-Path $env:ProgramFiles "OpenSSH\ssh.exe")
) | Where-Object { Test-Path $_ } | Select-Object -First 1
$keyPath = Join-Path $stateRoot "tunnel_ed25519"
$knownHostsPath = Join-Path $stateRoot "known_hosts"
$logPath = Join-Path $stateRoot "tunnel.log"

while ($true) {
    try {
        if ($null -eq $sshExe) {
            throw "OpenSSH client executable is unavailable."
        }
        if ((Test-Path $logPath) -and (Get-Item $logPath).Length -gt 2MB) {
            Move-Item $logPath "$logPath.previous" -Force
        }
        & $sshExe `
            -NT `
            -i $keyPath `
            -p 32736 `
            -R "127.0.0.1:22022:127.0.0.1:22" `
            -o "BatchMode=yes" `
            -o "IdentitiesOnly=yes" `
            -o "StrictHostKeyChecking=yes" `
            -o "UserKnownHostsFile=$knownHostsPath" `
            -o "ExitOnForwardFailure=yes" `
            -o "ServerAliveInterval=5" `
            -o "ServerAliveCountMax=3" `
            -o "TCPKeepAlive=yes" `
            "root@10.27.130.23" 2>> $logPath
    }
    catch {
        $_ | Out-String | Add-Content $logPath
    }
    Start-Sleep -Seconds 5
}
