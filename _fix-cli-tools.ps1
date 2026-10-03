# Repair Android command-line tools: clean download + tar extraction + verification.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$dest = 'C:\Users\hi\bin\android'
$sdk = Join-Path $dest 'sdk'
$zip = Join-Path $dest 'cmdline-tools.zip'
$url = 'https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip'
$env:JAVA_HOME = Join-Path $dest 'jdk17'
$expect = 153583359
function Log($m) { Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

function TryExtract {
    $tmp = Join-Path $dest 'cl-tmp'
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    # bsdtar (ships with Windows 10+) is far more tolerant than Expand-Archive
    & tar.exe -xf $zip -C $tmp 2>&1 | Out-String | Write-Host
    $sm = Join-Path $tmp 'cmdline-tools\bin\sdkmanager.bat'
    if (-not (Test-Path $sm)) { return $null }
    if ((Get-Item $sm).Length -lt 500) { return $null }
    return $tmp
}

$tmp = $null
if ((Test-Path $zip) -and ((Get-Item $zip).Length -eq $expect)) {
    Log 'trying tar on the existing zip...'
    $tmp = TryExtract
}
if (-not $tmp) {
    Log 're-downloading cmdline-tools cleanly...'
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    for ($i = 1; $i -le 5; $i++) {
        & curl.exe -L --retry 5 --retry-all-errors --connect-timeout 25 -s -o $zip $url
        if ((Test-Path $zip) -and ((Get-Item $zip).Length -eq $expect)) { break }
        Log ("  attempt {0} gave {1} bytes" -f $i, (Get-Item $zip -ErrorAction SilentlyContinue).Length)
    }
    if (-not ((Test-Path $zip) -and ((Get-Item $zip).Length -eq $expect))) { Log 'DOWNLOAD FAILED'; exit 1 }
    $tmp = TryExtract
}
if (-not $tmp) { Log 'EXTRACT FAILED'; exit 1 }

$clBase = Join-Path $sdk 'cmdline-tools'
New-Item -ItemType Directory -Force -Path $clBase | Out-Null
if (Test-Path (Join-Path $clBase 'latest')) { Remove-Item (Join-Path $clBase 'latest') -Recurse -Force }
Move-Item (Join-Path $tmp 'cmdline-tools') (Join-Path $clBase 'latest') -Force
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
$sm = Join-Path $clBase 'latest\bin\sdkmanager.bat'
Log ("sdkmanager.bat: " + (Test-Path $sm) + " (" + (Get-Item $sm).Length + " bytes)")
Log ("java: " + (Test-Path (Join-Path $env:JAVA_HOME 'bin\java.exe')))

Log 'sdkmanager --version:'
& $sm '--version' 2>&1 | Select-Object -Last 2 | Out-String | Write-Host

$sdkRoot = '--sdk_root=' + $sdk
$yes = (1..80 | ForEach-Object { 'y' })
Log 'accepting licenses...'
$yes | & $sm '--licenses' $sdkRoot 2>&1 | Select-Object -Last 2 | Out-String | Write-Host
foreach ($pkg in @('platform-tools', 'platforms;android-34', 'platforms;android-35', 'build-tools;34.0.0', 'build-tools;35.0.0')) {
    Log ("install " + $pkg)
    & $sm $pkg $sdkRoot 2>&1 | Select-Object -Last 3 | Out-String | Write-Host
}
Log '--- result ---'
foreach ($p in @('platform-tools\adb.exe', 'platforms\android-34\android.jar', 'platforms\android-35\android.jar', 'build-tools\34.0.0\aapt2.exe', 'build-tools\35.0.0\aapt2.exe', 'licenses')) {
    Log ("{0} -> {1}" -f $p, (Test-Path (Join-Path $sdk $p)))
}
Log 'DONE'
