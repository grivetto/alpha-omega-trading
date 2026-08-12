#!/bin/bash
echo "== BALANCE/EQUITY/ERROR lines in fleet journal =="
journalctl --user -u shadowgrid-fleet.service --since "6 hours ago" --no-pager 2>/dev/null | grep -iE "balance|equity|daily_start|error|fail|exception|auth" | tail -60
echo "== first 60 lines after last start =="
journalctl --user -u shadowgrid-fleet.service -n 400 --no-pager 2>/dev/null | awk '/Started shadowgrid-fleet/{n=NR} END{print "last_start_line="n}' 
journalctl --user -u shadowgrid-fleet.service -n 400 --no-pager 2>/dev/null | tail -400 | grep -vE "DAILY LOSS" | tail -40
