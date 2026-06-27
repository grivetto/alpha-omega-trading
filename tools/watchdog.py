#!/usr/bin/env python3
"""
Watchdog for denaro_navigator.py
Checks if the grid bot is running; if not, restarts it.
Logs to /home/sergio/denaro/watchdog.log
"""
import subprocess
import sys
import os
from datetime import datetime

LOG_FILE = "/home/sergio/denaro/watchdog.log"
BOT_SCRIPT = "/home/sergio/denaro/denaro_navigator.py"
VENV_PYTHON = "/home/sergio/denaro/venv/bin/python"
WORKDIR = "/home/sergio/denaro"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def is_bot_running():
    """Check if denaro_navigator.py process is active."""
    try:
        # Use pgrep to find the process
        result = subprocess.run(
            ["pgrep", "-f", "denaro_navigator.py"],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            # At least one PID found
            pids = result.stdout.strip().split()
            # Optional: verify it's not this watchdog itself
            for pid in pids:
                try:
                    out = subprocess.run(
                        ["ps", "-p", pid, "-o", "cmd="],
                        capture_output=True,
                        text=True,
                    )
                    if "denaro_navigator.py" in out.stdout and "watchdog" not in out.stdout:
                        return True
                except Exception:
                    pass
            return False
        return False
    except Exception as e:
        log(f"Error checking process: {e}")
        return False

def start_bot():
    """Start the bot in background using nohup."""
    try:
        # Ensure we're in the right directory
        os.chdir(WORKDIR)
        # Start the bot with nohup, redirecting output to grid_v4.log
        cmd = [
            "nohup",
            VENV_PYTHON,
            BOT_SCRIPT,
        ]
        with open(os.path.join(WORKDIR, "grid_v4.log"), "a") as logfile:
            proc = subprocess.Popen(
                cmd,
                stdout=logfile,
                stderr=subprocess.STDOUT,
            )
        log(f"Bot started with PID {proc.pid}")
        return True
    except Exception as e:
        log(f"Failed to start bot: {e}")
        return False

def main():
    log("Watchdog check started")
    if is_bot_running():
        log("Bot is running. No action needed.")
    else:
        log("Bot is NOT running. Attempting restart...")
        if start_bot():
            log("Restart successful.")
        else:
            log("Restart FAILED. Manual intervention required.")
            sys.exit(1)
    log("Watchdog check completed\n")

if __name__ == "__main__":
    main()