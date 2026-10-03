# Deploy + verify the vr-guardian student app on the Quest.
#   powershell -ExecutionPolicy Bypass -File _deploy-app.ps1
# Waits for the headset, installs, wires adb reverse, launches, then captures
# screenshots, hub state and app logs as evidence.
param(
    [int]$WaitSeconds = 600,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Continue'
$adb = 'C:\Users\hi\bin\platform-tools\adb.exe'
$apk = 'C:\Users\hi\Documents\vr-guardian-quest\app\build\outputs\apk\debug\app-debug.apk'
$pkg = 'mn.vrguardian.student'
$shotDir = 'C:\Users\hi\Documents\vr-student-app'

function Say($m) { Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

if (-not (Test-Path $apk)) { Say "APK missing: $apk"; exit 1 }

Say 'waiting for a headset on USB...'
$deadline = (Get-Date).AddSeconds($WaitSeconds)
$serial = $null
while ((Get-Date) -lt $deadline) {
    $line = (& $adb devices) 2>&1 | Select-String -Pattern '\s+device$' | Select-Object -First 1
    if ($line) { $serial = ($line.Line -split '\s+')[0]; break }
    Start-Sleep -Seconds 5
}
if (-not $serial) { Say 'no device appeared — connect the Quest over USB and re-run'; exit 1 }
Say "device: $serial"
if ($PSBoundParameters.ContainsKey('NoLaunch')) { } else { }

Say 'keeping it awake (proximity off)...'
& $adb -s $serial shell svc power stayon true 2>&1 | Out-Null
& $adb -s $serial shell am broadcast -a com.oculus.vrpowermanager.prox_close 2>&1 | Out-Null
& $adb -s $serial shell input keyevent KEYCODE_WAKEUP 2>&1 | Out-Null

Say 'installing APK...'
& $adb -s $serial install -r -g $apk 2>&1 | Select-Object -Last 3 | ForEach-Object { Say $_ }

Say 'wiring adb reverse tcp:8000 (USB hub route)...'
& $adb -s $serial reverse tcp:8000 tcp:8000 2>&1 | ForEach-Object { Say $_ }

if (-not $NoLaunch) {
    & $adb -s $serial logcat -c 2>&1 | Out-Null
    Say 'launching...'
    & $adb -s $serial shell am start -a android.intent.action.MAIN -c com.oculus.intent.category.VR -n "$pkg/.MainActivity" 2>&1 | ForEach-Object { Say $_ }
    Start-Sleep -Seconds 20
}

Say '--- app logs ---'
(& $adb -s $serial logcat -d -t 500) 2>&1 | Select-String -Pattern 'VrGuardian' | Select-Object -Last 20 | ForEach-Object { Say $_.Line }

Say '--- hub view of this headset ---'
try {
    $state = (Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/state' -UseBasicParsing -TimeoutSec 6).Content
    Say $state
} catch { Say ("hub unreachable: " + $_.Exception.Message) }

Say '--- screenshots ---'
foreach ($pair in @(@('launcher', 0), @('after-8s', 8))) {
    Start-Sleep -Seconds $pair[1]
    $out = Join-Path $shotDir ("_app_" + $pair[0] + ".png")
    if (Test-Path $out) { Remove-Item $out -Force }
    cmd /c "`"$adb`" -s $serial exec-out screencap -p > `"$out`"" 2>&1 | Out-Null
    if ((Test-Path $out) -and (Get-Item $out).Length -gt 1000) {
        Say ("{0} -> {1:N0} bytes" -f $out, (Get-Item $out).Length)
    } else {
        Say ("screenshot {0} came back empty (headset asleep / not worn)" -f $pair[0])
    }
}

Say 'done. If the panel is not visible, check the onSceneReady log above.'
