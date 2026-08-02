$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
    throw "This setup script must run in Windows PowerShell."
}

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) {
    throw "Python launcher 'py' was not found. Install 64-bit Python 3.11 or 3.12 from python.org, then reopen PowerShell."
}
& py -3 -c "import struct; assert struct.calcsize('P') == 8, '64-bit Python is required'; print('Python x64 OK')"
Assert-LastExitCode "Python architecture check"
& py -3 -m venv .venv
Assert-LastExitCode "Virtual environment creation"
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip setuptools wheel
Assert-LastExitCode "pip bootstrap"
& $venvPython -m pip install -r requirements-windows.txt
Assert-LastExitCode "PIPER dependency installation"
& $venvPython -c "import can, pyAgxArm, agx_cando; print('Windows CAN dependencies OK')"
Assert-LastExitCode "PIPER import check"

$tokenPath = Join-Path $PSScriptRoot "session-token.txt"
if (-not (Test-Path $tokenPath)) {
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    } finally {
        $generator.Dispose()
    }
    $token = ([BitConverter]::ToString($bytes) -replace '-', '').ToLowerInvariant()
    Set-Content -Path $tokenPath -Value $token -NoNewline -Encoding ascii
    Write-Host "Created session-token.txt"
} else {
    Write-Host "Keeping existing session-token.txt"
}

Write-Host "Setup complete. Do not run a motion demo. Start with start_observe.ps1."
