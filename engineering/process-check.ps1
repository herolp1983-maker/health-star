function Invoke-VerifiedProcess([string]$File,[string[]]$Arguments,[string]$Log) {
    # Requires PowerShell 7, as does the Android staging script.
    $ErrorActionPreference='Stop'
    $process=$null
    try {
        $command=Get-Command -Name $File -CommandType Application -ErrorAction Stop
        $info=[Diagnostics.ProcessStartInfo]::new()
        $info.FileName=$command.Source
        $info.UseShellExecute=$false
        $info.RedirectStandardOutput=$true
        $info.RedirectStandardError=$true
        $info.CreateNoWindow=$true
        $info.WorkingDirectory=(Get-Location).Path
        if([IO.Path]::GetExtension($command.Source) -in @('.cmd','.bat')){
            $parts=@($command.Source)+$Arguments
            # Batch callers here use fixed tool arguments, never shell expressions.
            foreach($part in $parts){if($part -match '[\r\n"%!&|<>^]'){throw 'Unsafe batch argument'}}
            $info.FileName=$env:ComSpec
            $quoted=($parts | ForEach-Object { '"'+$_+'"' }) -join ' '
            $info.Arguments='/d /s /c "'+$quoted+'"'
        }else{foreach($argument in $Arguments){$info.ArgumentList.Add($argument)}}
        $process=[Diagnostics.Process]::new();$process.StartInfo=$info
        if(!$process.Start()){throw 'Process did not start'}
        $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        [IO.File]::WriteAllText($Log,$stdout.GetAwaiter().GetResult()+$stderr.GetAwaiter().GetResult())
        return @{exit_code=$process.ExitCode;started=$true;log=$Log}
    } catch {
        $_.Exception.Message | Out-File -LiteralPath $Log -Append
        return @{exit_code=1;started=$false;log=$Log}
    } finally {if($null -ne $process){$process.Dispose()}}
}
