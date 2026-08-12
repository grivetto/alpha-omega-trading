echo "== shadowgrid-fleet.service unit (nuvola) =="
systemctl cat shadowgrid-fleet.service 2>/dev/null
echo "== denaro-mexc-marcodg1.service unit (MARCODG1) =="
systemctl cat denaro-mexc-marcodg1.service 2>/dev/null
echo "== denaro-kraken-health.service unit =="
systemctl cat denaro-kraken-health.service 2>/dev/null
echo "== env files in ~/denaro =="
ls -la ~/denaro/.env* 2>/dev/null
echo "== KRAKEN keys across denaro tree (masked, non-git) =="
grep -rInE "KRAKEN_(API|SECRET)" ~/denaro --include=".env*" 2>/dev/null | sed -E 's/=(.{6}).*/=\1.../' | head -20
echo "== all units env files referencing denaro =="
grep -rl "denaro" /etc/systemd/system/ 2>/dev/null | head; ls /etc/systemd/system/ | grep -iE "denaro|fleet|shadow" 2>/dev/null
echo "== fleet unit files in /etc/systemd =="
ls /etc/systemd/system/ | grep -iE "fleet|shadow|denaro" 2>/dev/null
