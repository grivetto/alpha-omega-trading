#!/usr/bin/env python3
"""Legion Bot Watchdog - checks if bot is alive, restarts if dead"""
import os, sys, subprocess, time, json
from pathlib import Path

HOME = Path.home()
BOT_NAME = "legion_bot"
SCREEN_CMD = f"screen -dmS {BOT_NAME} ./venv/bin/python legion_manager_production.py"

def check_screen():
    """Check if screen session exists"""
    try:
        r = subprocess.run(["screen", "-ls", BOT_NAME],
            capture_output=True, text=True, timeout=5)
        return BOT_NAME in r.stdout
    except:
        return False

def check_heartbeat(db_path=None, max_age=180):
    """Check if bot has recent heartbeat in DB"""
    if not db_path or not Path(db_path).exists():
        return False
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT MAX(last_heartbeat) FROM bot_state")
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            hb = float(row[0])
            return (time.time() - hb) < max_age
    except:
        pass
    return False

def restart_bot(project_dir):
    """Restart bot in screen"""
    os.chdir(project_dir)
    # Kill any existing bot process
    subprocess.run(["pkill", "-f", "legion_manager_production.py"],
        capture_output=True, timeout=5)
    time.sleep(2)
    # Start new screen session
    r = subprocess.run(SCREEN_CMD, shell=True, capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        print(f"[{time.strftime('%H:%M:%S')}] Bot restarted in {project_dir}")
        return True
    print(f"[{time.strftime('%H:%M:%S')}] Failed to restart bot: {r.stderr}")
    return False

def main():
    for config in [
        {"name": "mc2", "dir": "/home/sergio/denaro", "db": "/home/sergio/denaro/trades.db"},
        {"name": "MARCODG1", "dir": "/home/marco/denaro", "db": "/home/marco/denaro/trades.db"},
    ]:
        alive = check_screen() or check_heartbeat(config["db"])
        if not alive:
            if restart_bot(config["dir"]):
                pass
        else:
            pass  # Bot is alive

if __name__ == "__main__":
    main()
