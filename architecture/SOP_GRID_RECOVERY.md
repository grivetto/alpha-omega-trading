# SOP: Grid Recovery Procedure
**Layer 1 — Architecture**

## Purpose
Auto-recover a crashed or stalled grid bot on a remote node.

## Trigger Conditions
- Node status = DEAD for >120s (SSH fails 3x)
- Bot process not running
- Log file age >600s (bot silent)

## Recovery Steps

### Step 1: Verify Node Reachable
```
ssh <ssh_alias> "echo PING"
```
If fails → wait 60s → retry 3x → FAIL and escalate to Telegram alert

### Step 2: Kill Stale Processes
```
ssh <ssh_alias> "pkill -f 'grid_bot_v3.py'; pkill -f 'denaro_ultimate.py'"
```
Wait 2s

### Step 3: Start Grid Bot
**If node has systemd grid service:**
```
ssh <ssh_alias> "sudo systemctl start denaro-grid.service"
```
**Otherwise (screen-based):**
```
ssh <ssh_alias> "cd ~/denaro && screen -S denaro -dm bash -c 'source venv/bin/activate && python3 grid_bot_v3.py'"
```

### Step 4: Verify Bot Started
```
sleep 10
ssh <ssh_alias> "ps aux | grep grid_bot_v3 | grep -v grep"
```
- PID found → SUCCESS
- No PID → FAIL, retry Step 2-3 once more

### Step 5: Log Recovery Event
```
echo "RECOVERED|<node>|<timestamp>" >> ~/denaro/.tmp/recovery_log.txt
```

## Max Attempts
- 3 attempts per node per hour
- After 3 fails: Telegram alert "Node X recovery failed after 3 attempts"

## Safety
- Before restart: check disk space >10GB
- Before restart: check memory available >200MB
- NEVER start bot if previous attempt crashed <5min ago (crash loop detection)
