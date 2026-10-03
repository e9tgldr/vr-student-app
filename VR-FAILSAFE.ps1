# VR-FAILSAFE.ps1 - vr-student-app fail-safe (ASCII only, PS 5.1 safe)
#
# Modes:
#   (no args)   Fix + verify: start server if down, report status
#   -Check      Status only, change nothing
#   -Watch      Keep-alive daemon: auto-heal server every 5 s until stopped
#   -StopWatch  Stop the keep-alive daemon
#   -Stop       Kill the demo server
#
# Quest (USB):   http://localhost:8000/student.html
# Teacher (PC):  http://localhost:8000/teacher.html

param(
    [switch]$Check,
    [switch]$Watch,
    [switch]$StopWatch,
    [switch]$Stop
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py   = 'C:\Users\hi\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe'
$PidFile = Join-Path $env:TEMP 'vr-student-watch.pid'
$LogFile = Join-Path $Root 'vr-failsafe.log'

function Test-Server {
    return [bool](Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
}

function Start-ServerIfDown {
    if (Test-Server) { return $true }
    Write-Host '[fix] server down - starting under firewall-covered python...'
    Start-Process -FilePath $py -ArgumentList 'serve_app.py' -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Root 'vr-server.log') `
        -RedirectStandardError  (Join-Path $Root 'vr-server.err.log')
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Server) { Write-Host '[fix] server UP (port 8000)'; return $true }
    }
    Write-Host '[!!] server FAILED to start - check vr-server.err.log'
    return $false
}

function Stop-Server {
    $conns = Get-NetTCPConnection -LocalPort 8000,8001,8002,8003,8004,8005,8443,8444,8445,8446,8447,8448,8449 -State Listen -ErrorAction SilentlyContinue
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
        if ($proc -and $proc.Path -like '*python*') {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            Write-Host "[stop] killed server (pid $p)"
        }
    }
}

function Show-Status {
    $up = Test-Server
    $srv = 'DOWN'; if ($up) { $srv = 'UP  ' }
    Write-Host ("  server : {0} (port 8000)" -f $srv)
    return $up
}

# ---- stop server ----
if ($Stop) { Stop-Server; exit 0 }

# ---- stop watch daemon ----
if ($StopWatch) {
    if (Test-Path $PidFile) {
        $old = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($old) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "[watch] keep-alive daemon stopped (pid $old)"
    } else {
        Write-Host '[watch] no keep-alive daemon running'
    }
    exit 0
}

# ---- check ----
if ($Check) {
    Write-Host '=== vr-student-app status ==='
    $up = Show-Status
    if ($up) { exit 0 } else { exit 1 }
}

# ---- watch daemon ----
if ($Watch) {
    "watch start $(Get-Date -Format s)" | Add-Content $LogFile
    while ($true) {
        if (-not (Test-Server)) {
            [void](Start-ServerIfDown)
            "healed: server restarted $(Get-Date -Format s)" | Add-Content $LogFile
        }
        Start-Sleep -Seconds 5
    }
    exit 0
}

# ---- default: fix + verify ----
Write-Host '=== vr-student-app fail-safe ==='
$ok = Start-ServerIfDown
Write-Host ''
Write-Host '--- current status ---'
[void](Show-Status)
Write-Host ''
Write-Host 'Quest (USB):    http://localhost:8000/student.html'
Write-Host 'Teacher (PC):   http://localhost:8000/teacher.html'
if ($ok) { exit 0 } else { exit 1 }
