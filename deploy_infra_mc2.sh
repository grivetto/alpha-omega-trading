#!/bin/bash
# Deploy aggregator + dashboard come servizi systemd su mc2.
# Copiare questo script su MARCODG1 ed eseguirlo; raggiunge mc2 via tunnel 2222.

cat > /home/sergio/.deploy_infra_mc2.sh <<'REMOTE'
#!/bin/bash
set -e
echo "=== copio file fixati (se non già presenti) ==="
# aggregator già copiato da scp; il path di esecuzione è alpha-omega-trading
ls -la /home/sergio/alpha-omega-trading/denaro/infra_aggregator.py

echo "=== installo unit ==="
sudo cp /home/sergio/denaro/systemd/denaro-aggregator-mc2.service /etc/systemd/system/
sudo cp /home/sergio/denaro/systemd/denaro-dashboard-mc2.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "=== fermo processi manuali ==="
sudo pkill -f "serve_dashboard.py" 2>/dev/null || true
sudo pkill -f "infra_aggregator.py" 2>/dev/null || true
sleep 2

echo "=== avvio aggregator ==="
sudo systemctl enable denaro-aggregator-mc2.service 2>&1 | tail -1
sudo systemctl restart denaro-aggregator-mc2.service
sleep 3
echo "aggregator: $(systemctl is-active denaro-aggregator-mc2.service)"

echo "=== avvio dashboard ==="
sudo systemctl enable denaro-dashboard-mc2.service 2>&1 | tail -1
sudo systemctl restart denaro-dashboard-mc2.service
sleep 2
echo "dashboard: $(systemctl is-active denaro-dashboard-mc2.service)"

echo "=== test API locale ==="
curl -s -o /dev/null -w "infra 8912: HTTP %{http_code}\n" --max-time 5 http://127.0.0.1:8912/api/infra.json
curl -s -o /dev/null -w "dashb 8913: HTTP %{http_code}\n" --max-time 5 http://127.0.0.1:8913/dashboard
REMOTE
chmod +x /home/sergio/.deploy_infra_mc2.sh
# esecuzione remota su mc2 via tunnel
scp -o BatchMode=yes -P 2222 /home/sergio/.deploy_infra_mc2.sh sergio@127.0.0.1:/home/sergio/ 2>/dev/null && \
ssh -o BatchMode=yes -p 2222 sergio@127.0.0.1 "bash /home/sergio/.deploy_infra_mc2.sh" 2>&1 || echo "=== FAIL: tunnell o esecuzione remota fallita ==="
