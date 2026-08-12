#!/bin/bash
echo "== FLEET STATUS =="
systemctl --user is-active shadowgrid-fleet.service 2>/dev/null
FPID=$(pgrep -f "alpha_omega.fleet.coordinator" | head -1)
echo "fleet pid=$FPID"
echo "== FLEET JOURNAL (last 120) =="
journalctl --user -u shadowgrid-fleet.service -n 120 --no-pager 2>/dev/null | tail -120
