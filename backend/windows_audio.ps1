param(
    [Parameter(Mandatory=$true)][string]$AudioPath,
    [double]$Volume = 1
)
$ErrorActionPreference = 'Stop'
if ([System.IO.Path]::GetExtension($AudioPath) -eq '.wav') {
    # PCM volume is applied by the backend; system volume is left unchanged.
    $player = New-Object System.Media.SoundPlayer
    try {
        $player.SoundLocation = $AudioPath
        $player.Load()
        $player.PlaySync()
    } finally { $player.Dispose() }
} else {
    Add-Type -AssemblyName PresentationCore
    $player = New-Object System.Windows.Media.MediaPlayer
    try {
        $player.Open([Uri]$AudioPath)
        $player.Volume = [Math]::Max(0, [Math]::Min(1, $Volume))
        for ($i=0; $i -lt 100 -and -not $player.NaturalDuration.HasTimeSpan; $i++) {
            Start-Sleep -Milliseconds 50
        }
        if (-not $player.NaturalDuration.HasTimeSpan) { throw 'Windows kan het audiobestand niet openen.' }
        $player.Play()
        Start-Sleep -Milliseconds ([int]$player.NaturalDuration.TimeSpan.TotalMilliseconds + 350)
    } finally { $player.Close() }
}
