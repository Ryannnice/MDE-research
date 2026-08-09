param(
    [ValidateSet("piper", "piper_h", "piper_l", "piper_x")]
    [string]$Model = "piper_x",
    [ValidateSet("default", "v183", "v188", "v189")]
    [string]$Firmware = "default",
    [ValidateSet("none", "agx")]
    [string]$Gripper = "none",
    [string]$Channel = "0",
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Run setup_windows.ps1 first."
}

& $venvPython piper_bridge.py `
    --backend real `
    --mode observe `
    --model $Model `
    --firmware $Firmware `
    --gripper $Gripper `
    --interface agx_cando `
    --channel $Channel `
    --port $Port
