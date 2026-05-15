#!/bin/bash
# launch_legion.sh - lanciato via ssh, usa background
source /home/sergio/denaro/venv/bin/activate
cd /home/sergio/denaro
python3 -u legion_manager_production.py >> legion_production.log 2>&1