# Deploy Denaro — copia i file dal repo locale alle macchine via SCP.
# Eseguire da Windows (PowerShell):  .\scripts\deploy.ps1
# Il repo e' la fonte di verita': i file vengono copiati, MAI modificati a mano
# sulle macchine.

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

function Copy-ViaScp($src, $dst) {
  Write-Host "SCP: $src -> $dst"
  scp.exe -o ConnectTimeout=15 -o BatchMode=yes "$src" "$dst"
  if ($LASTEXITCODE -ne 0) { throw "scp fallito: $src" }
}

function Run-Ssh($hostname, $cmd) {
  Write-Host "SSH $hostname : $cmd"
  ssh.exe -o ConnectTimeout=15 -o BatchMode=yes $hostname $cmd
  if ($LASTEXITCODE -ne 0) { throw "ssh fallito su $hostname" }
}

Write-Host "==== DEPLOY DENARO ===="

# 1) Package Node (denaro/) -> MARCODG1 (clone del repo)
Write-Host "-- 1. package denaro/ -> MARCODG1 node app"
scp -r -o ConnectTimeout=15 -o BatchMode=yes "$ROOT\denaro" MARCODG1:/home/marco/denaro_node_app/ | Out-Null

# 2) Config -> MARCODG1 node app
Write-Host "-- 2. config/node.yaml -> MARCODG1"
Copy-ViaScp "$ROOT\config\node.yaml" "MARCODG1:/home/marco/denaro_node_app/config/node.yaml"

# 3) Motori/health/aggregator/dashboard -> MARCODG1 /home/marco/denaro
Write-Host "-- 3. infra+dashboard -> MARCODG1 /home/marco/denaro"
Copy-ViaScp "$ROOT\denaro\engine_solo_v33.py" "MARCODG1:/home/marco/denaro/engine_solo_v33.py"
Copy-ViaScp "$ROOT\denaro\health_server_v33.py" "MARCODG1:/home/marco/denaro/health_server_v33.py"
Copy-ViaScp "$ROOT\denaro\infra_aggregator.py" "MARCODG1:/home/marco/denaro/infra_aggregator.py"
Copy-ViaScp "$ROOT\denaro\infra_snapshot.py" "MARCODG1:/home/marco/denaro/infra_snapshot.py"
Copy-ViaScp "$ROOT\denaro\dashboard_infra.html" "MARCODG1:/home/marco/denaro/dashboard_infra.html"
Copy-ViaScp "$ROOT\denaro\dashboard_infra.html" "MARCODG1:/home/marco/denaro/dashboard_infra.html"

# 4) Dashboard servita da nginx (/var/www/html/dashboard)
Write-Host "-- 4. dashboard -> /var/www/html/dashboard (sudo)"
Run-Ssh MARCODG1 "sudo cp /home/marco/denaro/dashboard_infra.html /var/www/html/dashboard/index.html"

# 5) Zabbix push metrics -> MARCODG1
Write-Host "-- 5. push_metrics.py -> MARCODG1"
Copy-ViaScp "$ROOT\zabbix\push_metrics.py" "MARCODG1:/home/marco/denaro/zabbix/push_metrics.py"

# 6) Heal script -> mc2 (alertscripts montato nel container)
Write-Host "-- 6. denaro_heal.sh -> mc2 alertscripts"
Copy-ViaScp "$ROOT\zabbix\denaro_heal.sh" "mc2:/tmp/denaro_heal.sh"
Run-Ssh mc2 "sudo cp /tmp/denaro_heal.sh /home/sergio/zabbix-docker/alertscripts/denaro_heal.sh && sudo chmod 755 /home/sergio/zabbix-docker/alertscripts/denaro_heal.sh"

# 7) Unit systemd
Write-Host "-- 7. unit systemd"
Copy-ViaScp "$ROOT\systemd\denaro-node-paper.service" "MARCODG1:/tmp/denaro-node-paper.service"
Run-Ssh MARCODG1 "sudo cp /tmp/denaro-node-paper.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart denaro-node-paper"
Copy-ViaScp "$ROOT\systemd\zabbix-tunnel-reverse-mc2.service" "mc2:/tmp/zabbix-tunnel-reverse.service"
Run-Ssh mc2 "sudo cp /tmp/zabbix-tunnel-reverse.service /etc/systemd/system/zabbix-tunnel-reverse.service && sudo systemctl daemon-reload && sudo systemctl restart zabbix-tunnel-reverse"
Copy-ViaScp "$ROOT\systemd\denaro-health-marcodg1.service" "MARCODG1:/tmp/h.service"
Copy-ViaScp "$ROOT\systemd\denaro-aggregator-marcodg1.service" "MARCODG1:/tmp/a.service"
Run-Ssh MARCODG1 "sudo cp /tmp/h.service /etc/systemd/system/denaro-health-marcodg1.service && sudo cp /tmp/a.service /etc/systemd/system/denaro-aggregator-marcodg1.service && sudo systemctl daemon-reload && sudo systemctl restart denaro-health-marcodg1 denaro-aggregator-marcodg1"

Write-Host "==== DEPLOY COMPLETATO ===="

