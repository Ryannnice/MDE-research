param(
    [ValidateSet("piper", "piper_h", "piper_l", "piper_x")]
    [string]$Model = "piper_x",
    [ValidateSet("default", "v183", "v188", "v189")]
    [string]$Firmware = "default",
    [ValidateSet("none", "agx")]
    [string]$Gripper = "none",
    [string]$Channel = "0",
    [int]$Port = 0,
    [ValidateRange(1, 100)]
    [int]$MaxSpeedPercent = 5
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Run setup_windows.ps1 first."
}

Write-Host "CONTROL MODE: keep this window visible and stay beside the emergency stop."
& $venvPython piper_bridge.py `
    --backend real `
    --mode control `
    --model $Model `
    --firmware $Firmware `
    --gripper $Gripper `
    --interface agx_cando `
    --channel $Channel `
    --max-speed-percent $MaxSpeedPercent `
    --port $Port
