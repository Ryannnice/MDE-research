$ErrorActionPreference = "Stop"

$bridgeRoot = "C:\Desktop\PIPER\remote_control"
$pythonExe = Join-Path $bridgeRoot ".venv\Scripts\python.exe"
$bridgeScript = Join-Path $bridgeRoot "piper_bridge.py"
$logRoot = Join-Path $env:ProgramData "PiperRemote"
$logPath = Join-Path $logRoot "bridge-observe.log"

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
Set-Location $bridgeRoot
& $pythonExe `
    -u `
    $bridgeScript `
    --backend real `
    --mode observe `
    --model piper `
    --firmware v189 `
    --gripper agx `
    --interface agx_cando `
    --channel 0 `
    --port 57845 *> $logPath
