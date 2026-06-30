#!/usr/bin/env bash
# Denaro Deploy Script
# Usage: ./deploy.sh <host> <user>
#   ./deploy.sh nuvola sergio
#   ./deploy.sh MARCODG1 marco
set -euo pipefail

HOST="$1"
REMOTE_USER="$2"
REMOTE_DIR="/home/${REMOTE_USER}/denaro"
REPO_DIR="/home/sergio/alpha-omega-trading"

echo "=== Deploying Denaro to ${REMOTE_USER}@${HOST}:${REMOTE_DIR} ==="

# 1. Rsync code (exclude .venv, .git, .env)
rsync -avz --delete \
  --exclude='.venv/' \
  --exclude='.git/' \
  --exclude='.env' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='denaro_v3/' \
  --exclude='denaro_v6/' \
  --exclude='denaro_war/' \
  "${REPO_DIR}/denaro/" "${REMOTE_USER}@${HOST}:${REMOTE_DIR}/denaro/"
rsync -avz \
  "${REPO_DIR}/requirements.txt" \
  "${REPO_DIR}/.env.example" \
  "${REMOTE_USER}@${HOST}:${REMOTE_DIR}/"

# 2. Install/update venv + deps
ssh "${REMOTE_USER}@${HOST}" bash -c "'
cd ${REMOTE_DIR}
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt --upgrade
'"

# 3. Setup .env if not exists
ssh "${REMOTE_USER}@${HOST}" bash -c "'
cd ${REMOTE_DIR}
if [ ! -f .env ]; then
    cp .env.example .env
    echo \"=== IMPORTANTE: Modifica ${REMOTE_DIR}/.env con le tue API key ===\"
fi
'"

# 4. Install systemd service
SERVICE_NAME="denaro@${REMOTE_USER}"
SERVICE_FILE="${REMOTE_DIR}/denaro/tools/denaro@.service"
ssh "${REMOTE_USER}@${HOST}" bash -c "'
sudo cp ${SERVICE_FILE} /etc/systemd/system/${SERVICE_NAME}.service
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}.service
echo \"Servizio ${SERVICE_NAME} installato e abilitato\"
echo \"Per avviare: sudo systemctl start ${SERVICE_NAME}\"
'"

echo "=== Deploy completed for ${REMOTE_USER}@${HOST} ==="
echo "1. ssh ${REMOTE_USER}@${HOST}"
echo "2. nano ${REMOTE_DIR}/.env  # set API keys"
echo "3. sudo systemctl start ${SERVICE_NAME}"
echo "4. sudo journalctl -u ${SERVICE_NAME} -f"
