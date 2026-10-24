$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$projectRoot=Split-Path $PSScriptRoot -Parent
$toolsRoot=Join-Path $projectRoot '.tools'
New-Item -ItemType Directory -Path $toolsRoot -Force | Out-Null
function Get-VerifiedArchive($Uri,$Name,$Hash,$Algorithm='SHA256') {
    $archivePath=Join-Path $toolsRoot $Name
    if(!(Test-Path -LiteralPath $archivePath)){Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $archivePath -TimeoutSec 900}
    if((Get-FileHash -LiteralPath $archivePath -Algorithm $Algorithm).Hash.ToLowerInvariant() -ne $Hash.ToLowerInvariant()){throw "Checksum mismatch: $Name"}
    return $archivePath
}
if(!(Get-ChildItem -LiteralPath $toolsRoot -Directory -Filter 'jdk-*')){
    $jdkAssets=Invoke-RestMethod 'https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=x64&image_type=jdk&os=windows&vendor=eclipse'
    $jdkPackage=$jdkAssets[0].binary.package
    $jdkArchive=Get-VerifiedArchive $jdkPackage.link 'jdk.zip' $jdkPackage.checksum
    Expand-Archive -LiteralPath $jdkArchive -DestinationPath $toolsRoot -Force
    Write-Output 'JDK installed and SHA-256 verified.'
}
$sdkRoot=Join-Path $toolsRoot 'android-sdk'
if(!(Test-Path -LiteralPath "$sdkRoot/cmdline-tools/19.0/bin/sdkmanager.bat")){
    [xml]$sdkDocument=(Invoke-WebRequest -UseBasicParsing 'https://dl.google.com/android/repository/repository2-3.xml').Content
    $sdkPackage=$sdkDocument.SelectSingleNode("//*[local-name()='remotePackage' and @path='cmdline-tools;19.0']")
    $sdkArchive=$sdkPackage.SelectNodes(".//*[local-name()='archive']") | Where-Object { $_.SelectSingleNode("*[local-name()='host-os']").InnerText -eq 'windows' }
    $sdkComplete=$sdkArchive.SelectSingleNode("*[local-name()='complete']")
    $sdkUrl=$sdkComplete.SelectSingleNode("*[local-name()='url']").InnerText
    $sdkHash=$sdkComplete.SelectSingleNode("*[local-name()='checksum']").InnerText
    $sdkZip=Get-VerifiedArchive "https://dl.google.com/android/repository/$sdkUrl" 'sdk-tools-19.zip' $sdkHash 'SHA1'
    $sdkTemp=Join-Path $toolsRoot 'sdk19-extracted'
    Expand-Archive -LiteralPath $sdkZip -DestinationPath $sdkTemp -Force
    New-Item -ItemType Directory -Path "$sdkRoot/cmdline-tools" -Force | Out-Null
    # Both literal absolute targets stay within this project's .tools directory.
    $sourceResolved=[IO.Path]::GetFullPath("$sdkTemp/cmdline-tools")
    $targetResolved=[IO.Path]::GetFullPath("$sdkRoot/cmdline-tools/19.0")
    if(!$sourceResolved.StartsWith($toolsRoot,[StringComparison]::OrdinalIgnoreCase) -or !$targetResolved.StartsWith($toolsRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Invalid SDK target'}
    Move-Item -LiteralPath $sourceResolved -Destination $targetResolved
    Write-Output 'Android SDK command line tools installed and checksum verified.'
}
if(!(Test-Path -LiteralPath "$toolsRoot/gradle-8.11.1/bin/gradle.bat")){
    $gradleUri='https://services.gradle.org/distributions/gradle-8.11.1-bin.zip'
    $gradleResponse=(Invoke-WebRequest -UseBasicParsing "$gradleUri.sha256").Content
    if($gradleResponse -is [byte[]]){$gradleResponse=[Text.Encoding]::UTF8.GetString($gradleResponse)}
    $gradleHash=([string]$gradleResponse).Trim()
    $gradleZip=Get-VerifiedArchive $gradleUri 'gradle.zip' $gradleHash
    Expand-Archive -LiteralPath $gradleZip -DestinationPath $toolsRoot -Force
    Write-Output 'Gradle installed and SHA-256 verified.'
}
Write-Output 'Build tools ready. SDK package installation is a separate step.'
