# setup_win_autostart.ps1 -- Denaro/flotta: autostart agenti su Windows (PC NPOIT1H8446293K)
# Eseguire UNA VOLTA da una finestra PowerShell dell'utente sergio. Non serve admin.
# Idempotente: si puo' rieseguire senza danni. Non tocca ne' stampa segreti.
# Avvio:  powershell -NoProfile -ExecutionPolicy Bypass -File .\setup_win_autostart.ps1
#
# Cosa fa:
#   1) Docker Desktop -> autostart al logon (chiave Run dell'utente)
#   2) container "agent-zero" (A0-win) -> restart policy "unless-stopped" (+ avvio immediato)
#   3) task pianificato "DSH-Web" -> al logon avvia  npx @deepseek-ai/dsh web --no-open --port 3080
#      (finestra nascosta; log in %USERPROFILE%\dsh-web.log) + lo avvia subito
#   4) diagnostica agy (e' un CLI: nessun servizio da avviare)
# Transcript completo in %USERPROFILE%\setup_win_autostart.log

$ErrorActionPreference = 'Continue'
function T($m) { Write-Host ("[setup] " + $m) }

try { Start-Transcript -Path (Join-Path $env:USERPROFILE "setup_win_autostart.log") -Append | Out-Null } catch {}

Write-Host ("===== SETUP AUTOSTART -- " + (Get-Date -Format "yyyy-MM-dd HH:mm") + " =====")

# ---------- 1) Docker Desktop ----------
T "1) Docker Desktop -> autostart al logon..."
$dd = $null
$cands = @()
$appPath = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Docker Desktop.exe" -ErrorAction SilentlyContinue).'(default)'
if ($appPath) { $cands += $appPath }
$cands += (Join-Path ${env:ProgramFiles} "Docker\Docker\Docker Desktop.exe")
$cands += (Join-Path ${env:LOCALAPPDATA} "Docker\Docker Desktop.exe")
foreach ($c in $cands) { if ($c -and (Test-Path -LiteralPath $c)) { $dd = $c; break } }
if ($dd) {
  New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "Docker Desktop" -Value ('"' + $dd + '"') -PropertyType String -Force | Out-Null
  T ("   OK: " + $dd)
} else {
  T "   ATTENZIONE: Docker Desktop.exe non trovato nei percorsi standard."
}

# ---------- 2) container agent-zero (A0-win) ----------
T "2) Container A0 (agent-zero) -> restart policy 'unless-stopped'..."
$dockerExe = (Get-Command docker.exe -ErrorAction SilentlyContinue).Source
if (-not $dockerExe) { $dockerExe = (Get-Command docker -ErrorAction SilentlyContinue).Source }
if ($dockerExe) {
  $dockerOk = $false
  foreach ($i in 1..18) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break }
    if ($i -eq 1 -and $dd) { T "   Docker non risponde: avvio Docker Desktop e attendo (max ~3 min)..." ; Start-Process -FilePath $dd | Out-Null }
    Start-Sleep -Seconds 10
  }
  if ($dockerOk) {
    $names = @(docker ps -a --format "{{.Names}}" 2>$null | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    $target = $null
    if ($names -contains "agent-zero") { $target = "agent-zero" } else { $target = ($names | Where-Object { $_ -match "agent" } | Select-Object -First 1) }
    if ($target) {
      docker update --restart unless-stopped $target | Out-Null
      $running = (docker inspect -f "{{.State.Running}}" $target 2>$null)
      if ($running -notmatch "true") { docker start $target | Out-Null; $running = "avviato-ora" }
      $policy = (docker inspect -f "{{.HostConfig.RestartPolicy.Name}}" $target 2>$null)
      T ("   OK: " + $target + " -> running=" + $running + " restart=" + $policy)
    } else {
      T ("   ATTENZIONE: nessun container 'agent*'. Presenti: " + ($names -join ", "))
    }
  } else {
    T "   ATTENZIONE: docker non risponde. Avvia Docker Desktop e riesegui questo script."
  }
} else {
  T "   ATTENZIONE: comando docker non trovato (Docker Desktop installato?)."
}

# ---------- 3) task DSH-Web ----------
T "3) Task 'DSH-Web' (DSH web :3080) -> autostart al logon..."
$npx = (Get-Command npx.cmd -ErrorAction SilentlyContinue).Source
if (-not $npx) { $npx = (Get-Command npx -ErrorAction SilentlyContinue | Select-Object -First 1).Source }
if (-not $npx) {
  foreach ($c in @((Join-Path ${env:ProgramFiles} "nodejs\npx.cmd"), (Join-Path ${env:LOCALAPPDATA} "Programs\nodejs\npx.cmd"))) {
    if (Test-Path -LiteralPath $c) { $npx = $c; break }
  }
}
if ($npx) {
  $launcher = Join-Path $env:USERPROFILE "dsh-web-launch.ps1"
  $body = @"
# dsh-web-launch.ps1 -- generato da setup_win_autostart.ps1 (flotta Denaro)
Set-Location -LiteralPath `$env:USERPROFILE
`$log = Join-Path `$env:USERPROFILE "dsh-web.log"
& "NPXPATH" -y @deepseek-ai/dsh web --no-open --port 3080 *>> `$log
"@
  $body = $body.Replace("NPXPATH", $npx)
  Set-Content -LiteralPath $launcher -Value $body -Encoding UTF8
  $action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $launcher + '"')
  $trigger = New-ScheduledTaskTrigger -AtLogOn
  $set     = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
  $prin    = New-ScheduledTaskPrincipal -UserId ($env:USERDOMAIN + "\" + $env:USERNAME) -LogonType Interactive
  Register-ScheduledTask -TaskName "DSH-Web" -Action $action -Trigger $trigger -Settings $set -Principal $prin -Force -Description "DSH web :3080 (flotta Denaro) - autostart al logon" | Out-Null
  T ("   OK: task registrato -> " + $npx)
  Start-ScheduledTask -TaskName "DSH-Web"
  Start-Sleep -Seconds 6
  T ("   avvio immediato: stato=" + (Get-ScheduledTask -TaskName "DSH-Web").State)
} else {
  T "   ATTENZIONE: npx non trovato (Node.js installato per questo utente?)."
}

# ---------- 4) agy (diagnostica) ----------
T "4) agy (Antigravity CLI)..."
$agy = (Get-Command agy -ErrorAction SilentlyContinue).Source
if (-not $agy) { $agy = (Get-Command agy.exe -ErrorAction SilentlyContinue).Source }
if ($agy) {
  $v = ""
  try { $v = (& $agy --version 2>$null | Select-Object -First 1) } catch {}
  T ("   presente: " + $agy + " [" + $v + "]")
  T "   NOTA: agy e' un CLI (non un servizio): non c'e' nulla da mettere in autostart; si lancia quando serve."
} else {
  T "   agy non trovato nel PATH di questo utente."
}

# ---------- fine ----------
T ""
T "===== FATTO. Test: riavvia il PC; dopo il login, senza toccare nulla, devono tornare:"
T "  - A0-win   -> http://127.0.0.1:50080   (container agent-zero)"
T "  - DSH-web  -> http://127.0.0.1:3080    (task DSH-Web; log in %USERPROFILE%\dsh-web.log)"
T "Hermes (mc2) verifichera' da remoto."
T ""
Get-ScheduledTask -TaskName "DSH-Web" -ErrorAction SilentlyContinue | Select-Object TaskName, State | Format-Table -AutoSize | Out-String | Write-Host

try { Stop-Transcript | Out-Null } catch {}
