param([switch]$SkipWeb,[switch]$Offline)
$ErrorActionPreference='Stop'
$repoRoot=Split-Path $PSScriptRoot -Parent
$projectRoot=Join-Path $repoRoot 'hero-health-android'
$evidenceRoot=Join-Path $repoRoot '.engineering/local'
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
$results=[Collections.Generic.List[object]]::new()
. (Join-Path $PSScriptRoot 'process-check.ps1')
function Invoke-Check([string]$Name,[string]$File,[string[]]$Arguments) {
    $logPath=Join-Path $evidenceRoot ($Name+'.log')
    $result=Invoke-VerifiedProcess -File $File -Arguments $Arguments -Log $logPath
    $exitCode=$result.exit_code
    $results.Add(@{name=$Name;exit_code=$exitCode;started=$result.started;log=$logPath})
    Write-Output "$Name exit=$exitCode"
    if($exitCode -ne 0){throw "$Name failed. See local log: $logPath"}
}
try {
    Get-Command npm.cmd -CommandType Application -ErrorAction Stop | Out-Null
    $toolsRoot=Join-Path $projectRoot '.tools'
    $jdkFolder=Get-ChildItem -LiteralPath $toolsRoot -Directory -Filter 'jdk-*' | Select-Object -First 1
    if(!$jdkFolder){throw 'JDK missing; use existing project setup instructions first'}
    foreach($required in @("$($jdkFolder.FullName)/bin/java.exe","$toolsRoot/android-sdk/platforms/android-35/android.jar","$projectRoot/gradlew.bat")){
        if(!(Test-Path -LiteralPath $required -PathType Leaf)){throw "Required build tool missing: $required"}
    }
    Push-Location -LiteralPath $projectRoot
    try {
        if(!$SkipWeb){
            Invoke-Check 'domain-tests' 'npm.cmd' @('test')
            Invoke-Check 'web-build' 'npm.cmd' @('run','build:web')
        }
    } finally { Pop-Location }
    $toolsRoot=Join-Path $projectRoot '.tools'
    $jdkFolder=Get-ChildItem -LiteralPath $toolsRoot -Directory -Filter 'jdk-*' | Select-Object -First 1
    if(!$jdkFolder){throw 'JDK missing; use existing project setup instructions first'}
    $hash=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($projectRoot))).Substring(0,12).ToLowerInvariant()
    $tempBase=[IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $stageRoot=[IO.Path]::GetFullPath((Join-Path $tempBase "hero-engineering-$hash"))
    if(!$stageRoot.StartsWith($tempBase,[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe staging directory'}
    $marker=Join-Path $stageRoot '.engineering-owner'
    if((Test-Path -LiteralPath $stageRoot) -and (!(Test-Path -LiteralPath $marker) -or [IO.File]::ReadAllText($marker) -ne $projectRoot)){throw 'Staging owner mismatch'}
    New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null
    [IO.File]::WriteAllText($marker,$projectRoot)
    # Reuse the existing, verified-owner ASCII tool cache when present; no key copying.
    $existingBuild=Join-Path $tempBase "hero-health-build-$hash"
    $oldMarker=Join-Path $existingBuild '.hero-build-owner'
    if((Test-Path -LiteralPath $oldMarker) -and [IO.File]::ReadAllText($oldMarker) -eq $projectRoot){
        $asciiTools=Join-Path $existingBuild '.tools'
    }else{
        $asciiTools=Join-Path $stageRoot '.tools'
        New-Item -ItemType Directory -Path $asciiTools -Force | Out-Null
        foreach($toolName in @($jdkFolder.Name,'gradle-8.11.1','android-sdk','gradle-home')){
            if(!(Test-Path -LiteralPath "$asciiTools/$toolName")){Copy-Item -LiteralPath "$toolsRoot/$toolName" -Destination "$asciiTools/$toolName" -Recurse}
        }
    }
    $env:JAVA_HOME=Join-Path $asciiTools $jdkFolder.Name
    $env:ANDROID_HOME=Join-Path $asciiTools 'android-sdk'
    $env:GRADLE_USER_HOME=Join-Path $asciiTools 'gradle-home'
    $env:ANDROID_USER_HOME=Join-Path $stageRoot '.android'
    $env:PATH="$env:JAVA_HOME/bin;$env:PATH"
    foreach($file in @('settings.gradle','build.gradle','gradle.properties')){Copy-Item -LiteralPath "$projectRoot/$file" -Destination "$stageRoot/$file" -Force}
    foreach($file in @('gradlew','gradlew.bat')){Copy-Item -LiteralPath "$projectRoot/$file" -Destination "$stageRoot/$file" -Force}
    New-Item -ItemType Directory -Path "$stageRoot/gradle/wrapper" -Force | Out-Null
    foreach($file in @('gradle-wrapper.jar','gradle-wrapper.properties')){Copy-Item -LiteralPath "$projectRoot/gradle/wrapper/$file" -Destination "$stageRoot/gradle/wrapper/$file" -Force}
    New-Item -ItemType Directory -Path "$stageRoot/app" -Force | Out-Null
    $sourceTarget=[IO.Path]::GetFullPath((Join-Path $stageRoot 'app/src'))
    if(!$sourceTarget.StartsWith($stageRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe source replacement target'}
    if(Test-Path -LiteralPath $sourceTarget){Remove-Item -LiteralPath $sourceTarget -Recurse -Force}
    Copy-Item -LiteralPath "$projectRoot/app/src" -Destination $sourceTarget -Recurse
    Copy-Item -LiteralPath "$projectRoot/app/build.gradle" -Destination "$stageRoot/app/build.gradle" -Force
    if(Test-Path -LiteralPath "$stageRoot/signing.properties"){throw 'Unexpected release signing configuration in debug-check workspace'}
    New-Item -ItemType Directory -Path $env:ANDROID_USER_HOME -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $stageRoot 'local.properties'),"sdk.dir=$($env:ANDROID_HOME.Replace('\','/'))`n")
    Push-Location -LiteralPath $stageRoot
    try {
        $gradleOptions=@('--no-daemon','--console=plain',':app:testDebugUnitTest',':app:lintDebug',':app:assembleDebug')
        if($Offline){$gradleOptions=@('--offline')+$gradleOptions}
        Invoke-Check 'android-debug' "$stageRoot/gradlew.bat" $gradleOptions
    }finally{Pop-Location}
    # Copy only test/lint evidence, never signing data or APKs.
    $jvmEvidence=Join-Path $evidenceRoot ('jvm-'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $jvmEvidence -Force | Out-Null
    Get-ChildItem -LiteralPath "$stageRoot/app/build/test-results/testDebugUnitTest" -Filter 'TEST-*.xml' | Copy-Item -Destination $jvmEvidence -Force
    foreach($item in @('app/build/reports/lint-results-debug.xml','app/build/reports/lint-results-debug.html')){
        $source=Join-Path $stageRoot $item
        if(Test-Path -LiteralPath $source){Copy-Item -LiteralPath $source -Destination $evidenceRoot -Recurse -Force}
    }
    $scope=if($SkipWeb){'android-debug-only'}else{'web-domain-and-android-debug'}
    @{status='PASS';checks=@($results);stage=$stageRoot;jvm_evidence=$jvmEvidence;scope=$scope;utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$evidenceRoot/results.json" -Encoding utf8
    Write-Output "PASS: $scope. Independent review gate is separate; this alone does not mark delivery Ready."
}catch{
    @{status='FAIL';checks=@($results);reason=$_.Exception.Message;utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$evidenceRoot/results.json" -Encoding utf8
    throw
}
