# ABILITA-SSH.ps1 -- canale di comando Hermes (mc2) -> questo PC (NPOIT1H8446293K)
# Eseguire UNA VOLTA in PowerShell COME AMMINISTRATORE (tasto destro sul menu Start ->
# "Terminale (amministratore)").
# Non serve NESSUNA password: autorizza solo la CHIAVE PUBBLICA di mc2.
# La chiave privata resta su mc2 e non esce mai da li'.

Write-Host "== 1) Installo OpenSSH Server (puo' metterci 1-2 minuti) =="
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd

Write-Host "== 2) Firewall: porta 22 in ingresso =="
if (-not (Get-NetFirewallRule -Name "sshd" -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -Name "sshd" -DisplayName "OpenSSH Server (sshd)" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
}

Write-Host "== 3) Autorizzo la chiave di Hermes =="
$k = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExKk0cSngn2/dG1BB4s+Kq3Jqu0XobLlaol8+rWT4Lq hermes@mc2 (accesso win)'
$f = "$env:ProgramData\ssh\administrators_authorized_keys"
if (-not (Test-Path $f)) { New-Item -ItemType File -Path $f | Out-Null }
if (-not (Select-String -Path $f -SimpleMatch $k -Quiet)) { Add-Content -Path $f -Value $k }
icacls $f /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F" | Out-Null
# copia di sicurezza anche per utente non-admin:
$d = "$env:USERPROFILE\.ssh"
New-Item -ItemType Directory -Force -Path $d | Out-Null
if (-not (Select-String -Path "$d\authorized_keys" -SimpleMatch $k -Quiet -ErrorAction SilentlyContinue)) { Add-Content -Path "$d\authorized_keys" -Value $k }

Write-Host ""
Write-Host "== FATTO. Manda a Hermes QUESTA riga (utente Windows): =="
whoami
Get-Service sshd | Select-Object Name, Status, StartType | Format-Table -AutoSize
Write-Host "(poi Hermes prova la connessione: ssh <utente>@100.76.22.119)"
