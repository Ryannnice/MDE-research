$ErrorActionPreference = "Stop"

$taskName = "PIPER Bridge Observe"
$stateRoot = Join-Path $env:ProgramData "PiperRemote"
$runnerPath = Join-Path $stateRoot "run_bridge_observe.ps1"
$powerShellExe = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path $runnerPath)) {
    throw "Bridge runner is missing: $runnerPath"
}

$action = New-ScheduledTaskAction `
    -Execute $powerShellExe `
    -Argument "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$runnerPath`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -User "SYSTEM" `
    -RunLevel Highest `
    -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Start-Sleep -Seconds 2
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State
