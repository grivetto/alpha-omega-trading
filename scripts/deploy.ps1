# Deploy Denaro — copia i file dal repo locale alle macchine via SCP.
# Eseguire da Windows (PowerShell):  .\scripts\deploy.ps1
# Il repo e' la fonte di verita': i file vengono copiati, MAI modificati a mano
# sulle macchine.

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

function Scp($src, $dst) {
  Write-Host "SCP: $src -> $dst"
  scp -o ConnectTimeout=15 -o BatchMode=yes "$src" "$dst"
  if ($LASTEXITCODE -ne 0) { throw "scp fallito: $src" }
}

function Ssh($hostname, $cmd) {
  Write-Host "SSH $hostname : $cmd"
  ssh -o ConnectTimeout=15 -o BatchMode=yes $hostname $cmd
  if ($LASTEXITCODE -ne 0) { throw "ssh fallito su $hostname" }
}

Write-Host "==== DEPLOY DENARO ===="

# 1) Package Node (denaro/) -> MARCODG1 (clone del repo)
Write-Host "-- 1. package denaro/ -> MARCODG1 node app"
scp -r -o ConnectTimeout=15 -o BatchMode=yes "$ROOT\denaro" MARCODG1:/home/marco/denaro_node_app/ | Out-Null

# 2) Config -> MARCODG1 node app
Write-Host "-- 2. config/node.yaml -> MARCODG1"
Scp "$ROOT\config\node.yaml" "MARCODG1:/home/marco/denaro_node_app/config/node.yaml"

# 3) Motori/health/aggregator/dashboard -> MARCODG1 /home/marco/denaro
Write-Host "-- 3. infra+dashboard -> MARCODG1 /home/marco/denaro"
Scp "$ROOT\denaro\engine_solo_v33.py" "MARCODG1:/home/marco/denaro/engine_solo_v33.py"
Scp "$ROOT\denaro\health_server_v33.py" "MARCODG1:/home/marco/denaro/health_server_v33.py"
Scp "$ROOT\denaro\infra_aggregator.py" "MARCODG1:/home/marco/denaro/infra_aggregator.py"
Scp "$ROOT\denaro\infra_snapshot.py" "MARCODG1:/home/marco/denaro/infra_snapshot.py"
Scp "$ROOT\denaro\dashboard_infra.html" "MARCODG1:/home/marco/denaro/dashboard_infra.html"
Scp "$ROOT\denaro\dashboard_infra.html" "MARCODG1:/home/marco/denaro/dashboard_infra.html"

# 4) Dashboard servita da nginx (/var/www/html/dashboard)
Write-Host "-- 4. dashboard -> /var/www/html/dashboard (sudo)"
Ssh MARCODG1 "sudo cp /home/marco/denaro/dashboard_infra.html /var/www/html/dashboard/index.html"

# 5) Zabbix push metrics -> MARCODG1
Write-Host "-- 5. push_metrics.py -> MARCODG1"
Scp "$ROOT\zabbix\push_metrics.py" "MARCODG1:/home/marco/denaro/zabbix/push_metrics.py"

# 6) Heal script -> mc2 (alertscripts montato nel container)
Write-Host "-- 6. denaro_heal.sh -> mc2 alertscripts"
Scp "$ROOT\zabbix\denaro_heal.sh" "mc2:/tmp/denaro_heal.sh"
Ssh mc2 "sudo cp /tmp/denaro_heal.sh /home/sergio/zabbix-docker/alertscripts/denaro_heal.sh && sudo chmod 755 /home/sergio/zabbix-docker/alertscripts/denaro_heal.sh"

# 7) Unit systemd
Write-Host "-- 7. unit systemd"
Scp "$ROOT\systemd\denaro-node-paper.service" "MARCODG1:/tmp/denaro-node-paper.service"
Ssh MARCODG1 "sudo cp /tmp/denaro-node-paper.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart denaro-node-paper"
Scp "$ROOT\systemd\zabbix-tunnel-reverse-mc2.service" "mc2:/tmp/zabbix-tunnel-reverse.service"
Ssh mc2 "sudo cp /tmp/zabbix-tunnel-reverse.service /etc/systemd/system/zabbix-tunnel-reverse.service && sudo systemctl daemon-reload && sudo systemctl restart zabbix-tunnel-reverse"
Scp "$ROOT\systemd\denaro-health-marcodg1.service" "MARCODG1:/tmp/h.service"
Scp "$ROOT\systemd\denaro-aggregator-marcodg1.service" "MARCODG1:/tmp/a.service"
Ssh MARCODG1 "sudo cp /tmp/h.service /etc/systemd/system/denaro-health-marcodg1.service && sudo cp /tmp/a.service /etc/systemd/system/denaro-aggregator-marcodg1.service && sudo systemctl daemon-reload && sudo systemctl restart denaro-health-marcodg1 denaro-aggregator-marcodg1"

Write-Host "==== DEPLOY COMPLETATO ===="
