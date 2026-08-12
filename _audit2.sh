echo "== UNITS (denaro|fleet|shadow|alpha) =="
systemctl list-unit-files --no-pager | grep -iE "denaro|fleet|shadow|alpha"
echo "== RUNNING SERVICES =="
systemctl list-units --type=service --state=running --no-pager | grep -iE "denaro|fleet|shadow|alpha"
echo "== FLEET PID cgroup =="
cat /proc/444368/cgroup 2>/dev/null
echo "== main_mexc.py exchange refs =="
grep -nE "okx|kraken|mexc|bybit|ccxt\." /home/sergio/denaro/main_mexc.py 2>/dev/null | head -25
echo "== mexc_engine.py exchange refs =="
grep -nE "class |ccxt\.|okx|mexc|bybit|kraken" /home/sergio/denaro/mexc_engine.py 2>/dev/null | head -25
echo "== fleet config nuvola =="
cat /home/sergio/denaro/config/fleet_config_nuvola.json 2>/dev/null | head -70
echo "== denaro-mexc-nuvola journal (last 25) =="
journalctl -u denaro-mexc-nuvola.service -n 25 --no-pager 2>/dev/null
echo "== fleet units journal (last 8) =="
for u in fleet-coordinator.service shadowgrid-fleet.service shadowgrid@.service; do
  echo "--- $u ---"
  journalctl -u $u -n 8 --no-pager 2>/dev/null | tail -8
done
