param([switch]$SetupSdk,[switch]$SkipWeb)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$projectRoot=Split-Path $PSScriptRoot -Parent
if(!(Test-Path -LiteralPath (Join-Path $projectRoot 'signing.properties') -PathType Leaf)){
    throw 'Original signing.properties is required. Restore the provisioned release signing identity; this build never generates a replacement key.'
}
Set-Location -LiteralPath $projectRoot
$toolsRoot=Join-Path $projectRoot '.tools'
$jdkFolder=Get-ChildItem -LiteralPath $toolsRoot -Directory -Filter 'jdk-*' | Select-Object -First 1
if(!$jdkFolder){throw 'Run scripts/setup-tools.ps1 first'}
$env:JAVA_HOME=$jdkFolder.FullName
$env:ANDROID_HOME=Join-Path $toolsRoot 'android-sdk'
$env:ANDROID_USER_HOME=Join-Path $toolsRoot 'android-user'
$env:GRADLE_USER_HOME=Join-Path $toolsRoot 'gradle-home'
$env:PATH="$env:JAVA_HOME/bin;$env:PATH"
$sdkManager=Join-Path $env:ANDROID_HOME 'cmdline-tools/19.0/bin/sdkmanager.bat'
if($SetupSdk){
    # Install only this app's required packages and their SDK license.
    (('y'+[Environment]::NewLine)*10) | & $sdkManager "--sdk_root=$env:ANDROID_HOME" 'platforms;android-35' 'build-tools;35.0.0' 'platform-tools'
    if($LASTEXITCODE -ne 0){throw 'SDK package download failed'}
}
if(!(Test-Path -LiteralPath "$env:ANDROID_HOME/platforms/android-35/android.jar")){throw 'Android SDK 35 missing; rerun with -SetupSdk'}
$sdkProperty=$env:ANDROID_HOME.Replace('\','/')
[IO.File]::WriteAllText((Join-Path $projectRoot 'local.properties'),"sdk.dir=$sdkProperty`n",(New-Object Text.UTF8Encoding($false)))
if(!$SkipWeb){& npm.cmd run build:web;if($LASTEXITCODE -ne 0){throw 'Web build failed'}}
$compileRoot=$projectRoot
$compileTools=$toolsRoot
if($projectRoot -match '[^\x00-\x7F]'){
    # Android tools and Gradle worker classpaths on Windows require an ASCII staging directory.
    $hashBytes=[Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($projectRoot))
    $projectId=([BitConverter]::ToString($hashBytes)).Replace('-','').Substring(0,12).ToLowerInvariant()
    $tempBase=[IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $compileRoot=[IO.Path]::GetFullPath((Join-Path $tempBase "hero-health-build-$projectId"))
    if(!$compileRoot.StartsWith($tempBase,[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe staging target'}
    $markerPath=Join-Path $compileRoot '.hero-build-owner'
    if((Test-Path -LiteralPath $compileRoot) -and !(Test-Path -LiteralPath $markerPath)){throw 'Staging directory is not owned by this project'}
    if((Test-Path -LiteralPath $markerPath) -and [IO.File]::ReadAllText($markerPath) -ne $projectRoot){throw 'Staging owner mismatch'}
    New-Item -ItemType Directory -Path $compileRoot -Force | Out-Null
    [IO.File]::WriteAllText($markerPath,$projectRoot)
    $compileTools=Join-Path $compileRoot '.tools'
    New-Item -ItemType Directory -Path $compileTools -Force | Out-Null
    foreach($toolName in @($jdkFolder.Name,'gradle-8.11.1')){
        if(!(Test-Path -LiteralPath "$compileTools/$toolName")){Copy-Item -LiteralPath "$toolsRoot/$toolName" -Destination "$compileTools/$toolName" -Recurse}
    }
    foreach($sdkPart in @('platforms','build-tools','platform-tools','licenses')){
        New-Item -ItemType Directory -Path "$compileTools/android-sdk" -Force | Out-Null
        if(!(Test-Path -LiteralPath "$compileTools/android-sdk/$sdkPart")){Copy-Item -LiteralPath "$toolsRoot/android-sdk/$sdkPart" -Destination "$compileTools/android-sdk/$sdkPart" -Recurse}
    }
    if(!(Test-Path -LiteralPath "$compileTools/gradle-home/caches")){
        New-Item -ItemType Directory -Path "$compileTools/gradle-home" -Force | Out-Null
        Copy-Item -LiteralPath "$toolsRoot/gradle-home/caches" -Destination "$compileTools/gradle-home/caches" -Recurse
    }
    foreach($fileName in @('settings.gradle','build.gradle','gradle.properties','signing.properties')){Copy-Item -LiteralPath (Join-Path $projectRoot $fileName) -Destination (Join-Path $compileRoot $fileName) -Force}
    New-Item -ItemType Directory -Path "$compileRoot/app" -Force | Out-Null
    foreach($subDir in @('app/src','.keys')){
        $stageTarget=[IO.Path]::GetFullPath((Join-Path $compileRoot $subDir))
        # Verified literal paths and ownership marker before replacing only our staging copies.
        if(!$stageTarget.StartsWith($compileRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe staging copy target'}
        if(Test-Path -LiteralPath $stageTarget){Remove-Item -LiteralPath $stageTarget -Recurse -Force}
        Copy-Item -LiteralPath (Join-Path $projectRoot $subDir) -Destination $stageTarget -Recurse
    }
    Copy-Item -LiteralPath "$projectRoot/app/build.gradle" -Destination "$compileRoot/app/build.gradle" -Force
    $env:JAVA_HOME=Join-Path $compileTools $jdkFolder.Name
    $env:ANDROID_HOME=Join-Path $compileTools 'android-sdk'
    $env:GRADLE_USER_HOME=Join-Path $compileTools 'gradle-home'
    $env:PATH="$env:JAVA_HOME/bin;$env:PATH"
    [IO.File]::WriteAllText((Join-Path $compileRoot 'local.properties'),"sdk.dir=$($env:ANDROID_HOME.Replace('\','/'))`n",(New-Object Text.UTF8Encoding($false)))
    Write-Output "Compiling in ASCII staging directory: $compileRoot"
}
Set-Location -LiteralPath $compileRoot
& "$compileTools/gradle-8.11.1/bin/gradle.bat" --no-daemon --console=plain :app:testReleaseUnitTest :app:lintRelease :app:assembleRelease
if($LASTEXITCODE -ne 0){throw 'Android build or checks failed'}
$deliveryRoot=Join-Path $projectRoot 'delivery'
New-Item -ItemType Directory -Path $deliveryRoot -Force | Out-Null
$appVersion=(Get-Content -LiteralPath (Join-Path $projectRoot 'package.json') -Raw | ConvertFrom-Json).version
$apkPath=Join-Path $deliveryRoot ("健康星-$appVersion.apk")
Copy-Item -LiteralPath "$compileRoot/app/build/outputs/apk/release/app-release.apk" -Destination $apkPath -Force
& "$env:ANDROID_HOME/build-tools/35.0.0/apksigner.bat" verify --verbose --print-certs $apkPath
if($LASTEXITCODE -ne 0){throw 'APK signature validation failed'}
Get-FileHash -LiteralPath $apkPath -Algorithm SHA256 | Format-List
$verificationRoot=Join-Path $projectRoot 'verification'
New-Item -ItemType Directory -Path $verificationRoot -Force | Out-Null
Copy-Item -LiteralPath "$compileRoot/app/build/reports/lint-results-release.html" -Destination $verificationRoot -Force
Copy-Item -LiteralPath "$compileRoot/app/build/reports/lint-results-release.xml" -Destination $verificationRoot -Force
Copy-Item -LiteralPath "$compileRoot/app/build/test-results/testReleaseUnitTest" -Destination "$verificationRoot/unit-tests" -Recurse -Force
Set-Location -LiteralPath $projectRoot
Write-Output 'Signed local Android APK ready.'
