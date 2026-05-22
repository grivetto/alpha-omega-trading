#!/bin/bash
# Deploy Denaro Memory System to mc2
# Copy all memory modules
# Run this from the workspace root
set -e

MC2="sergio@192.168.1.99 -p 2222"
MC2_DIR="/home/sergio/denaro"
LOCAL_DIR="."

echo "=== Deploying Denaro Memory System ==="

# 1. Copy core modules
scp -P 2222 -o ConnectTimeout=10 "$LOCAL_DIR/denaro_memory.py" "$MC2:$MC2_DIR/"
scp -P 2222 -o ConnectTimeout=10 "$LOCAL_DIR/regime_detector.py" "$MC2:$MC2_DIR/"
scp -P 2222 -o ConnectTimeout=10 "$LOCAL_DIR/strategy_optimizer.py" "$MC2:$MC2_DIR/"
scp -P 2222 -o ConnectTimeout=10 "$LOCAL_DIR/memorize_trades.py" "$MC2:$MC2_DIR/"

# 2. Copy updated orchestrator (requires restart)
scp -P 2222 -o ConnectTimeout=10 "$LOCAL_DIR/orchestrator.py" "$MC2:$MC2_DIR/"

# 3. Set permissions
ssh $MC2 "chmod +x $MC2_DIR/*.py"

# 4. Initialize memory DB
ssh $MC2 "cd $MC2_DIR && python3 denaro_memory.py"

# 5. Restart orchestrator
ssh $MC2 "sudo systemctl restart denaro-orchestrator 2>/dev/null || sudo killall -1 python3 orchestrator.py 2>/dev/null; echo 'Orchestrator restarted'"

echo "=== Deploy complete ==="
echo "Memory DB initialized at $MC2_DIR/denaro_memory.db"
echo "Regime detector runs manually: python3 regime_detector.py"
echo "Strategy optimizer runs manually: python3 strategy_optimizer.py"
echo "API endpoints available at http://192.168.1.99:8899/api/memory/summary"
