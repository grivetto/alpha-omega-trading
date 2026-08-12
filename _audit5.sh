echo "== USER UNITS =="
ls -la ~/.config/systemd/user/ 2>/dev/null | grep -iE "fleet|shadow|denaro"
echo "== shadowgrid unit env files =="
for u in shadowgrid-okx.service shadowgrid-kraken.service shadowgrid-fleet.service; do
  f=~/.config/systemd/user/$u
  [ -f "$f" ] || f=/etc/systemd/system/$u
  echo "--- $u ($f) ---"
  cat "$f" 2>/dev/null | grep -E "EnvironmentFile|ExecStart|WorkingDirectory|Environment="
done
echo "== fleet user journal (last 40) =="
journalctl --user -u shadowgrid-okx.service -n 40 --no-pager 2>/dev/null | tail -40
journalctl --user -u shadowgrid-kraken.service -n 40 --no-pager 2>/dev/null | tail -40
journalctl --user -u shadowgrid-fleet.service -n 40 --no-pager 2>/dev/null | tail -40
echo "== all user units with fleet/shadow =="
systemctl --user list-units --all --no-pager 2>/dev/null | grep -iE "fleet|shadow|denaro" | head -20
echo "== fleet coordinator child bots =="
FPID=$(pgrep -f "alpha_omega.fleet.coordinator" | head -1)
ps --ppid $FPID -o pid,cmd --no-headers 2>/dev/null | head -20
echo "== coordinator log file =="
ls -la ~/denaro/logs/ 2>/dev/null | head; find ~/denaro -name "*.log" -newer ~/denaro/.env 2>/dev/null | head -10
