#!/bin/bash
# Deploy Alpha-Omega Trading System (Unified Engine)
# Usage: ./deploy_alpha_omega.sh [nuvola|marcodg1|mc2|all]

set -euo pipefail

REPO_URL="https://github.com/grivetto/alpha-omega-trading.git"
BRANCH="main"
DEPLOY_DIR_NUVOLA="/home/sergio/denaro"
DEPLOY_DIR_MARCODG1="/home/marco/dev/alpha-omega-trading/denaro"
DEPLOY_DIR_MC2="/opt/alpha-omega-trading"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; }

stop_legacy_services() {
    local host=$1
    log "Stopping legacy services on $host..."
    ssh $host << 'EOF'
        # Stop shadowgrid-fleet user service
        systemctl --user stop shadowgrid-fleet 2>/dev/null || true
        systemctl --user disable shadowgrid-fleet 2>/dev/null || true
        
        # Stop any shadowgrid@ services
        for svc in $(systemctl list-units --type=service --state=running | grep shadowgrid | awk '{print $1}'); do
            sudo systemctl stop $svc 2>/dev/null || true
            sudo systemctl disable $svc 2>/dev/null || true
        done
        
        # Kill any remaining python shadowgrid processes
        pkill -f "shadowgrid" 2>/dev/null || true
        pkill -f "shadowgrid_fleet" 2>/dev/null || true
        
        echo "Legacy services stopped on $host"
EOF
}

deploy_to_node() {
    local host=$1
    local deploy_dir=$2
    local role=$3  # trading or coordinator
    
    log "Deploying to $host ($role) at $deploy_dir..."
    
    ssh $host << EOF
        set -euo pipefail
        
        # Backup existing config if exists
        if [ -d "$deploy_dir" ]; then
            mv "$deploy_dir" "${deploy_dir}.backup.$(date +%s)"
        fi
        
        # Clone repo
        git clone -b $BRANCH $REPO_URL "$deploy_dir"
        cd "$deploy_dir"
        
        # Create virtual environment
        python3 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
        
        # Copy environment file
        if [ ! -f .env ]; then
            cp docker/.env.example .env
            echo "EDIT .env with your API keys before starting!"
        fi
        
        echo "Deploy completed on $host"
EOF
}

setup_systemd_services() {
    local host=$1
    local deploy_dir=$2
    local role=$3
    
    log "Setting up systemd services on $host ($role)..."
    
    if [ "$role" = "coordinator" ]; then
        ssh $host << EOF
            sudo cp $deploy_dir/systemd/fleet-coordinator.service /etc/systemd/system/
            sudo systemctl daemon-reload
            sudo systemctl enable fleet-coordinator
            echo "Coordinator service installed"
EOF
    else
        ssh $host << EOF
            # User service for fleet coordinator
            mkdir -p ~/.config/systemd/user
            cp $deploy_dir/systemd/shadowgrid-fleet.service ~/.config/systemd/user/
            systemctl --user daemon-reload
            systemctl --user enable shadowgrid-fleet
            
            # Per-bot template (optional, for individual bot management)
            sudo cp $deploy_dir/systemd/shadowgrid@.service /etc/systemd/system/
            sudo systemctl daemon-reload
            
            echo "Trading node services installed"
EOF
    fi
}

start_services() {
    local host=$1
    local role=$2
    
    log "Starting services on $host ($role)..."
    
    if [ "$role" = "coordinator" ]; then
        ssh $host "sudo systemctl start fleet-coordinator"
        sleep 3
        ssh $host "sudo systemctl status fleet-coordinator --no-pager"
    else
        ssh $host "systemctl --user start shadowgrid-fleet"
        sleep 3
        ssh $host "systemctl --user status shadowgrid-fleet --no-pager"
    fi
}

verify_health() {
    local host=$1
    local port=$2
    local name=$3
    
    log "Verifying health on $name ($host:$port)..."
    
    # Try health endpoint with retries
    for i in {1..5}; do
        if ssh $host "curl -sf http://127.0.0.1:$port/health" 2>/dev/null; then
            log "✅ Health check passed for $name"
            return 0
        fi
        sleep 2
    done
    
    error "❌ Health check failed for $name after 5 attempts"
    return 1
}

main() {
    local target=${1:-all}
    
    case $target in
        nuvola)
            stop_legacy_services "nuvola"
            deploy_to_node "nuvola" "$DEPLOY_DIR_NUVOLA" "trading"
            setup_systemd_services "nuvola" "$DEPLOY_DIR_NUVOLA" "trading"
            start_services "nuvola" "trading"
            verify_health "nuvola" 8900 "nuvola"
            ;;
        marcodg1)
            stop_legacy_services "MARCODG1"
            deploy_to_node "MARCODG1" "$DEPLOY_DIR_MARCODG1" "trading"
            setup_systemd_services "MARCODG1" "$DEPLOY_DIR_MARCODG1" "trading"
            start_services "MARCODG1" "trading"
            verify_health "MARCODG1" 8900 "MARCODG1"
            ;;
        mc2)
            deploy_to_node "mc2" "$DEPLOY_DIR_MC2" "coordinator"
            setup_systemd_services "mc2" "$DEPLOY_DIR_MC2" "coordinator"
            start_services "mc2" "coordinator"
            verify_health "mc2" 8080 "mc2"
            ;;
        all)
            # Deploy to mc2 first (coordinator)
            deploy_to_node "mc2" "$DEPLOY_DIR_MC2" "coordinator"
            setup_systemd_services "mc2" "$DEPLOY_DIR_MC2" "coordinator"
            
            # Deploy to trading nodes in parallel
            stop_legacy_services "nuvola" &
            stop_legacy_services "MARCODG1" &
            wait
            
            deploy_to_node "nuvola" "$DEPLOY_DIR_NUVOLA" "trading" &
            deploy_to_node "MARCODG1" "$DEPLOY_DIR_MARCODG1" "trading" &
            wait
            
            setup_systemd_services "nuvola" "$DEPLOY_DIR_NUVOLA" "trading" &
            setup_systemd_services "MARCODG1" "$DEPLOY_DIR_MARCODG1" "trading" &
            wait
            
            # Start coordinator first
            start_services "mc2" "coordinator"
            sleep 5
            
            # Start trading nodes
            start_services "nuvola" "trading" &
            start_services "MARCODG1" "trading" &
            wait
            
            # Verify all
            verify_health "mc2" 8080 "mc2"
            verify_health "nuvola" 8900 "nuvola"
            verify_health "MARCODG1" 8900 "MARCODG1"
            ;;
        *)
            echo "Usage: $0 [nuvola|marcodg1|mc2|all]"
            exit 1
            ;;
    esac
    
    log "Deployment completed for $target"
}

main "$@"
