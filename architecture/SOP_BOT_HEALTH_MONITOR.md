# SOP: Bot Health Monitor
**Layer 1 — Architecture**

## Purpose
Determine if a Denaro node and its grid bot are healthy or need intervention.

## Input
- `node_name`: Human name (e.g., "MARCODG1")
- `ssh_alias`: SSH alias from ~/.ssh/config (e.g., "MARCODG1")

## Health Check Procedure

### Step 1: SSH Connectivity
```
ssh <ssh_alias> "echo PING" → expect "PING"
Timeout: 10s → fail
Retries: 3
```

### Step 2: Bot Process Check
```
ssh <ssh_alias> "ps aux | grep grid_bot_v3 | grep -v grep"
```
- If no PID → **status: DEAD**
- If PID found → continue

### Step 3: Log Freshness Check
```
ssh <ssh_alias> "stat -c %Y /home/*/denaro/*.log 2>/dev/null || stat -c %Y ~/denaro/*.log"
```
Age in seconds:
- <60s → OK
- 60-300s → DEGRADED
- >300s → DEAD (bot zombie)

### Step 4: Memory Check
```
ssh <ssh_alias> "free -m | grep Mem"
```
- available_mb < 200 → DEGRADED

### Step 5: Load Check
```
uptime | awk -F'load average:' '{print $2}'
```
- load[0] > 8.0 → DEGRADED

## Output
Returns JSON Node Health Response (see gemini.md section 2)

## Edge Cases
- SSH key mismatch → returns status: DEAD, error: "SSH_AUTH_FAILURE"
- Bot running but in paused state → status: DEGRADED
- Multiple grid_bot processes → KILL EXTRA PIDS, warn
