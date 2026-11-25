# audio.ps1: the laptop's audio for a VSL take (knowledge#14099). Run by `vsl prep` from Ra; copied to C:\vsl\_tools\.
#
# Tyler 2026-11-16 2:38 AM MT: "I just won't use the DJI." REVERSED 2026-11-17 10:10-10:17 PM (five asks for the DJI mic):
# the DJI's endpoints are left alone. Playback = the laptop speakers, no OTHER Bluetooth audio endpoint may stay enabled,
# recording = the first present -Recording pattern (vsl passes the DJI first, then the laptop array).
#
#   -Part setup        over ssh (elevated): install AudioDeviceCmdlets for this user when missing, and DISABLE every
#                      enabled Bluetooth audio endpoint (headset, hands-free, headphones, speaker). Each one disabled is
#                      appended to C:\vsl\bt-disabled.txt, so `-Part restore` can bring it back.
#   -Part default      in Tyler's session (fast.py ps): set default AND communication playback to -Playback and
#                      recording to the first present -Recording pattern, then read all four back.
#   -Part restore      over ssh (elevated): re-enable what setup disabled, and empty the list.
#   -DryRun            change nothing; say what would change.
#
# The LAST line of output is one JSON object: {"part","ok","did":[...],"problems":[...], ...}. vsl reads only that line.
param([ValidateSet('setup', 'default', 'restore')][string]$Part = 'setup', [string]$Playback = 'Speakers \(Senary Audio\)',
      [string[]]$Recording = @('Microphone Array \(Senary Audio\)'), [switch]$DryRun)
$ErrorActionPreference = 'Continue'; $ProgressPreference = 'SilentlyContinue'
$did = @(); $problems = @(); $extra = [ordered]@{}
$list = 'C:\vsl\bt-disabled.txt'
New-Item -ItemType Directory -Force C:\vsl | Out-Null

# A Bluetooth audio endpoint: its name in parentheses is a paired Bluetooth device's name ("Headset (DJI Mic Mini-5A67E3
# Hands-Free)", "Headphones (2- JLab GO Pop+)", "Speakers (JBL Flip 3)"), or it says Hands-Free.
function BtEndpoints {
  $bt = @(Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | % FriendlyName)
  Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue | ? {
    $inner = if ($_.FriendlyName -match '\((?:\d+- )?(.+?)(?: Hands-Free)?\)$') { $Matches[1] } else { '' }
    $_.FriendlyName -notmatch 'DJI' -and (($inner -and $bt -contains $inner) -or $_.FriendlyName -match 'Hands-Free') }
}

if ($Part -eq 'setup') {
  if (-not (Get-Module -ListAvailable AudioDeviceCmdlets)) {
    if ($DryRun) { $did += 'WOULD install AudioDeviceCmdlets (CurrentUser)' }
    else {
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      if (-not (Get-PackageProvider -ListAvailable NuGet -ErrorAction SilentlyContinue)) { Install-PackageProvider NuGet -MinimumVersion 2.8.5.201 -Scope CurrentUser -Force | Out-Null }
      Install-Module AudioDeviceCmdlets -Scope CurrentUser -Force -AllowClobber -ErrorAction SilentlyContinue
      if (Get-Module -ListAvailable AudioDeviceCmdlets) { $did += 'installed AudioDeviceCmdlets' } else { $problems += 'AudioDeviceCmdlets did not install' }
    }
  }
  foreach ($e in @(BtEndpoints | ? Status -eq 'OK')) {
    if ($DryRun) { $did += "WOULD disable Bluetooth endpoint '$($e.FriendlyName)'"; continue }
    Disable-PnpDevice -InstanceId $e.InstanceId -Confirm:$false -ErrorAction SilentlyContinue
    if ((Get-PnpDevice -InstanceId $e.InstanceId).Status -ne 'OK') { $did += "disabled Bluetooth endpoint '$($e.FriendlyName)'"; Add-Content $list $e.InstanceId }
    else { $problems += "could not disable Bluetooth endpoint '$($e.FriendlyName)'" }
  }
  $left = @(BtEndpoints | ? Status -eq 'OK' | % FriendlyName)
  if ($left -and -not $DryRun) { $problems += "Bluetooth endpoint(s) still enabled: $($left -join ', ')" }
  $extra.bt_enabled = $left
}
elseif ($Part -eq 'restore') {
  $ids = @(if (Test-Path $list) { Get-Content $list | ? { $_ -match '\S' } | Sort-Object -Unique })
  foreach ($id in $ids) {
    if ($DryRun) { $did += "WOULD enable $id"; continue }
    Enable-PnpDevice -InstanceId $id -Confirm:$false -ErrorAction SilentlyContinue; $did += "enabled $((Get-PnpDevice -InstanceId $id).FriendlyName)"
  }
  if (-not $DryRun) { Remove-Item $list -ErrorAction SilentlyContinue }
}
else {
  Import-Module AudioDeviceCmdlets -ErrorAction SilentlyContinue
  if (-not (Get-Command Set-AudioDevice -ErrorAction SilentlyContinue)) { $problems += 'AudioDeviceCmdlets missing (vsl prep runs -Part setup first)' }
  else {
    $all = @(Get-AudioDevice -List)
    $play = $all | ? { $_.Type -eq 'Playback' -and $_.Name -match $Playback } | Select -First 1
    $rec = $null; foreach ($p in $Recording) { $rec = $all | ? { $_.Type -eq 'Recording' -and $_.Name -match $p } | Select -First 1; if ($rec) { break } }
    if (-not $play) { $problems += "no playback device matches '$Playback'" }
    if (-not $rec) { $problems += "no recording device matches $($Recording -join ' or ')" }
    foreach ($d in @($play, $rec) | ? { $_ }) {
      if ($DryRun) { $did += "WOULD set default + communication $($d.Type.ToLower()) to '$($d.Name)'" }
      else { Set-AudioDevice -ID $d.ID | Out-Null; $did += "default + communication $($d.Type.ToLower()) -> '$($d.Name)'" }
    }
    $now = [ordered]@{ playback = (Get-AudioDevice -Playback).Name; playback_comm = (Get-AudioDevice -PlaybackCommunication).Name
                       recording = (Get-AudioDevice -Recording).Name; recording_comm = (Get-AudioDevice -RecordingCommunication).Name }
    $extra.now = $now
    if (-not $DryRun -and $play -and ($now.playback -ne $play.Name -or $now.playback_comm -ne $play.Name)) { $problems += "playback reads back as '$($now.playback)' / '$($now.playback_comm)'" }
    if (-not $DryRun -and $rec -and ($now.recording -ne $rec.Name -or $now.recording_comm -ne $rec.Name)) { $problems += "recording reads back as '$($now.recording)' / '$($now.recording_comm)'" }
    $extra.recording_name = if ($rec) { $rec.Name } else { $null }
  }
}
$out = [ordered]@{ part = $Part; dry_run = [bool]$DryRun; ok = ($problems.Count -eq 0); did = $did; problems = $problems }
foreach ($k in $extra.Keys) { $out[$k] = $extra[$k] }
$out | ConvertTo-Json -Compress -Depth 4
