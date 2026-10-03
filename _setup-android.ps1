# Android toolchain installer v2 — curl-based (PowerShell's Invoke-WebRequest
# stalls on large files from this network). Safe to re-run: resumes/skips.
# Installs into C:\Users\hi\bin\android : jdk17\ + sdk\ (cmdline-tools, platform-tools,
# platforms;android-34/35, build-tools;34.0.0/35.0.0)
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$dest = 'C:\Users\hi\bin\android'
$sdk  = Join-Path $dest 'sdk'
$jdkDir = Join-Path $dest 'jdk17'
New-Item -ItemType Directory -Force -Path $dest, $sdk | Out-Null
function Log($m) { $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m; Write-Host $line }

function Fetch($url, $out, $minMB) {
    # curl with resume + retries; validates a minimum size before returning $true
    for ($i = 1; $i -le 6; $i++) {
        Log ("  curl attempt {0}: {1}" -f $i, (Split-Path $out -Leaf))
        & curl.exe -L -C - --retry 4 --retry-delay 3 --retry-all-errors --connect-timeout 25 `
            --speed-time 60 --speed-limit 20000 -s -o $out $url
        if (Test-Path $out) {
            $mb = (Get-Item $out).Length / 1MB
            Log ("  -> {0:N1} MB" -f $mb)
            if ($mb -ge $minMB) { return $true }
        }
    }
    return $false
}

# ---------- 1. JDK 17 (Eclipse Temurin, official Adoptium API) ----------
if (-not (Test-Path (Join-Path $jdkDir 'bin\java.exe'))) {
    $jdkZip = Join-Path $dest 'jdk17.zip'
    if (-not (Test-Path $jdkZip) -or (Get-Item $jdkZip).Length -lt 120MB) {
        Log 'jdk: downloading Temurin 17 (windows x64)...'
        if (-not (Fetch 'https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse' $jdkZip 120)) {
            Log 'jdk: DOWNLOAD FAILED'
        }
    }
    if (Test-Path $jdkZip) {
        Log 'jdk: extracting...'
        if (Test-Path $jdkDir) { Remove-Item $jdkDir -Recurse -Force }
        New-Item -ItemType Directory -Force -Path $jdkDir | Out-Null
        Expand-Archive -Path $jdkZip -DestinationPath $jdkDir -Force
        $inner = Get-ChildItem $jdkDir -Directory | Select-Object -First 1
        if ($inner -and -not (Test-Path (Join-Path $jdkDir 'bin\java.exe'))) {
            Get-ChildItem $inner.FullName -Force | Move-Item -Destination $jdkDir -Force
            Remove-Item $inner.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
$java = Join-Path $jdkDir 'bin\java.exe'
if (Test-Path $java) { Log ("jdk: OK -> " + (& $java -version 2>&1 | Select-Object -First 1)) } else { Log 'jdk: MISSING (stop)'; exit 1 }

# ---------- 2. Android command-line tools ----------
$clBase = Join-Path $sdk 'cmdline-tools'
$clBin  = Join-Path $clBase 'latest\bin\sdkmanager.bat'
if (-not (Test-Path $clBin)) {
    $clZip = Join-Path $dest 'cmdline-tools.zip'
    if (-not (Test-Path $clZip) -or (Get-Item $clZip).Length -lt 80MB) {
        Log 'cmdline-tools: downloading...'
        if (-not (Fetch 'https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip' $clZip 80)) {
            Log 'cmdline-tools: DOWNLOAD FAILED (stop)'; exit 1
        }
    }
    $tmp = Join-Path $dest 'cl-tmp'
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive -Path $clZip -DestinationPath $tmp -Force
    New-Item -ItemType Directory -Force -Path $clBase | Out-Null
    if (Test-Path (Join-Path $clBase 'latest')) { Remove-Item (Join-Path $clBase 'latest') -Recurse -Force }
    Move-Item (Join-Path $tmp 'cmdline-tools') (Join-Path $clBase 'latest') -Force
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
if (-not (Test-Path $clBin)) { Log 'cmdline-tools: MISSING (stop)'; exit 1 }
Log 'cmdline-tools: OK'

# ---------- 3. SDK components ----------
$env:JAVA_HOME = $jdkDir
$env:ANDROID_HOME = $sdk
$sdkRoot = '--sdk_root=' + $sdk
Log 'sdkmanager: accepting licenses...'
$yes = (1..60 | ForEach-Object { 'y' })
$yes | & $clBin '--licenses' $sdkRoot 2>&1 | Select-Object -Last 2 | Out-String | Write-Host
foreach ($pkg in @('platform-tools', 'platforms;android-34', 'platforms;android-35', 'build-tools;34.0.0', 'build-tools;35.0.0')) {
    Log ("sdkmanager: " + $pkg)
    & $clBin $pkg $sdkRoot 2>&1 | Select-Object -Last 3 | Out-String | Write-Host
}
Log '--- result ---'
foreach ($p in @('platform-tools\adb.exe', 'platforms\android-34\android.jar', 'platforms\android-35\android.jar', 'build-tools\34.0.0\aapt2.exe', 'build-tools\35.0.0\aapt2.exe')) {
    Log ("{0} -> {1}" -f $p, (Test-Path (Join-Path $sdk $p)))
}
Log 'DONE'
