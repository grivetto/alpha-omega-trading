#!/usr/bin/env python3
import os, subprocess, time, logging, sys

# Force venv python
VENV_PYTHON = '/home/marco/denaro/venv/bin/python3'
if sys.executable != VENV_PYTHON:
    os.execv(VENV_PYTHON, [VENV_PYTHON, __file__])

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [WATCHDOG] %(message)s',
    handlers=[
        logging.FileHandler('/home/marco/denaro/logs/watchdog.log'),
        logging.StreamHandler()
    ]
)

BASE = '/home/marco/denaro'
BOT  = 'grid_bot_v3.py'

def is_running():
    try:
        with open('/proc/loadavg') as f:
            pass
    except:
        pass
    for fn in os.listdir('/proc'):
        if fn.isdigit():
            try:
                with open(f'/proc/{fn}/cmdline', 'rb') as cf:
                    cmd = cf.read().decode('utf-8', errors='ignore')
                    if BOT in cmd and 'python' in cmd.lower():
                        return True
            except:
                pass
    return False

def launch():
    cmd = [VENV_PYTHON, os.path.join(BASE, BOT)]
    logging.info(f'Launching: {" ".join(cmd)}')
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

def main():
    logging.info('=== DENARO WATCHDOG STARTED ===')
    if not is_running():
        launch()
        time.sleep(2)
    while True:
        if not is_running():
            logging.warning(f'{BOT} DOWN → restarting')
            launch()
        time.sleep(10)

if __name__ == '__main__':
    main()
