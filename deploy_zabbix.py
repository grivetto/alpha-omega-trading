#!/usr/bin/env python3
"""Deploy Zabbix V3 configs to all servers"""
import subprocess

configs = {
    "mc2": """# Denaro V3 Zabbix Monitoring - mc2 (Hub)
UserParameter=denaro.v3.service.orchestrator,pgrep -f orchestrator.py > /dev/null 2>&1 && echo 1 || echo 0
UserParameter=denaro.v3.service.zabbix_agent,pgrep -f zabbix_agentd > /dev/null 2>&1 && echo 1 || echo 0
UserParameter=denaro.v3.bot.squadra,pgrep -f orchestrator.py > /dev/null 2>&1 && echo 1 || echo 0
UserParameter=denaro.v3.portfolio.eur,python3 /home/sergio/denaro/zabbix_metrics.py portfolio.eur 2>/dev/null || echo 0
UserParameter=denaro.v3.portfolio.total,python3 /home/sergio/denaro/zabbix_metrics.py portfolio.total 2>/dev/null || echo 0
UserParameter=denaro.v3.orders.total,python3 /home/sergio/denaro/zabbix_metrics.py orders.total 2>/dev/null || echo 0
UserParameter=denaro.v3.orders.sol,python3 /home/sergio/denaro/zabbix_metrics.py orders.sol 2>/dev/null || echo 0
UserParameter=denaro.v3.orders.ada,python3 /home/sergio/denaro/zabbix_metrics.py orders.ada 2>/dev/null || echo 0
UserParameter=denaro.v3.price.sol,python3 /home/sergio/denaro/zabbix_metrics.py price.sol 2>/dev/null || echo 0
UserParameter=denaro.v3.price.eth,python3 /home/sergio/denaro/zabbix_metrics.py price.eth 2>/dev/null || echo 0
UserParameter=denaro.v3.price.btc,python3 /home/sergio/denaro/zabbix_metrics.py price.btc 2>/dev/null || echo 0
UserParameter=denaro.v3.price.ada,python3 /home/sergio/denaro/zabbix_metrics.py price.ada 2>/dev/null || echo 0
UserParameter=denaro.v3.bnb.balance,python3 /home/sergio/denaro/zabbix_metrics.py bnb.balance 2>/dev/null || echo 0
UserParameter=denaro.v3.load.1m,cat /proc/loadavg | awk '{print $1}'
UserParameter=denaro.v3.mem.pct,free -m | grep Mem | awk '{printf "%.0f", $3/$2 * 100}'
UserParameter=denaro.v3.disk.pct,df / | tail -1 | awk '{print $5}' | tr -d '%'
UserParameter=denaro.v3.watchdog.all_ok,c=0; pgrep -f orchestrator.py > /dev/null 2>&1 && c=1; pgrep -f zabbix_agentd > /dev/null 2>&1 && c=1; echo $c
""",
    "nuvola": """# Denaro V3 Zabbix Monitoring - Nuvola (SOL Grid)
UserParameter=denaro.v3.service.zabbix_agent,pgrep -f zabbix_agentd > /dev/null 2>&1 && echo 1 || echo 0
UserParameter=denaro.v3.bot.sol_grid,pgrep -f 'denaro_v3.py.*SOL' > /dev/null 2>&1 && echo 1 || echo 0
UserParameter=denaro.v3.price.sol,python3 /home/sergio/denaro/zabbix_metrics.py price.sol 2>/dev/null || echo 0
UserParameter=denaro.v3.price.ada,python3 /home/sergio/denaro/zabbix_metrics.py price.ada 2>/dev/null || echo 0
UserParameter=denaro.v3.orders.sol,python3 /home/sergio/denaro/zabbix_metrics.py orders.sol 2>/dev/null || echo 0
UserParameter=denaro.v3.orders.ada,python3 /home/sergio/denaro/zabbix_metrics.py orders.ada 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.sol.buys,python3 /home/sergio/denaro/zabbix_grid_metric.py buys 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.sol.sells,python3 /home/sergio/denaro/zabbix_grid_metric.py sells 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.sol.invested,python3 /home/sergio/denaro/zabbix_grid_metric.py invested 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.sol.profit,python3 /home/sergio/denaro/zabbix_grid_metric.py profit 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.sol.fills,python3 /home/sergio/denaro/zabbix_grid_metric.py fills 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.sol.eur_free,python3 /home/sergio/denaro/zabbix_grid_metric.py eur_free 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.sol.compound,python3 /home/sergio/denaro/zabbix_grid_metric.py compound 2>/dev/null || echo 1
UserParameter=denaro.v3.grid.sol.errors,grep -c ERROR /home/sergio/denaro/denaro_v3.log 2>/dev/null || echo 0
UserParameter=denaro.v3.load.1m,cat /proc/loadavg | awk '{print $1}'
UserParameter=denaro.v3.mem.pct,free -m | grep Mem | awk '{printf "%.0f", $3/$2 * 100}'
UserParameter=denaro.v3.disk.pct,df / | tail -1 | awk '{print $5}' | tr -d '%'
UserParameter=denaro.v3.watchdog.all_ok,c=0; pgrep -f 'denaro_v3.py.*SOL' > /dev/null 2>&1 && c=1; pgrep -f zabbix_agentd > /dev/null 2>&1 && c=1; echo $c
""",
    "MARCODG1": """# Denaro V3 Zabbix Monitoring - MARCODG1 (ADA Grid)
UserParameter=denaro.v3.service.zabbix_agent,pgrep -f zabbix_agentd > /dev/null 2>&1 && echo 1 || echo 0
UserParameter=denaro.v3.bot.ada_grid,pgrep -f 'denaro_v3.py.*ADA' > /dev/null 2>&1 && echo 1 || echo 0
UserParameter=denaro.v3.price.ada,python3 /home/sergio/denaro/zabbix_metrics.py price.ada 2>/dev/null || echo 0
UserParameter=denaro.v3.price.sol,python3 /home/sergio/denaro/zabbix_metrics.py price.sol 2>/dev/null || echo 0
UserParameter=denaro.v3.orders.ada,python3 /home/sergio/denaro/zabbix_metrics.py orders.ada 2>/dev/null || echo 0
UserParameter=denaro.v3.orders.sol,python3 /home/sergio/denaro/zabbix_metrics.py orders.sol 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.ada.buys,python3 /home/sergio/denaro/zabbix_grid_metric.py buys 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.ada.sells,python3 /home/sergio/denaro/zabbix_grid_metric.py sells 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.ada.invested,python3 /home/sergio/denaro/zabbix_grid_metric.py invested 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.ada.profit,python3 /home/sergio/denaro/zabbix_grid_metric.py profit 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.ada.fills,python3 /home/sergio/denaro/zabbix_grid_metric.py fills 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.ada.eur_free,python3 /home/sergio/denaro/zabbix_grid_metric.py eur_free 2>/dev/null || echo 0
UserParameter=denaro.v3.grid.ada.compound,python3 /home/sergio/denaro/zabbix_grid_metric.py compound 2>/dev/null || echo 1
UserParameter=denaro.v3.grid.ada.errors,grep -c ERROR /home/sergio/denaro/denaro_v3.log 2>/dev/null || echo 0
UserParameter=denaro.v3.load.1m,cat /proc/loadavg | awk '{print $1}'
UserParameter=denaro.v3.mem.pct,free -m | grep Mem | awk '{printf "%.0f", $3/$2 * 100}'
UserParameter=denaro.v3.disk.pct,df / | tail -1 | awk '{print $5}' | tr -d '%'
UserParameter=denaro.v3.watchdog.all_ok,c=0; pgrep -f 'denaro_v3.py.*ADA' > /dev/null 2>&1 && c=1; pgrep -f zabbix_agentd > /dev/null 2>&1 && c=1; echo $c
"""
}

for host, conf in configs.items():
    # Write config to remote host
    cmd = f"ssh {host} \"cat > /tmp/denaro_v3.conf << 'ENDCONF'\\n{conf}\\nENDCONF\""
    print(f"Deploying to {host}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
    else:
        # Move to correct location and restart
        restart_cmd = f"ssh {host} 'sudo mv /tmp/denaro_v3.conf /etc/zabbix/zabbix_agentd.d/denaro_v3.conf && sudo chmod 644 /etc/zabbix/zabbix_agentd.d/denaro_v3.conf && sudo systemctl restart zabbix-agent'"
        result2 = subprocess.run(restart_cmd, shell=True, capture_output=True, text=True)
        if result2.returncode != 0:
            print(f"  RESTART ERROR: {result2.stderr}")
        else:
            print(f"  OK")

print("Done!")
