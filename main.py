import logging
import os
import socket
import subprocess
import time
from pathlib import Path

import psutil
from decouple import config

# ====== CONFIG - change these to match your environment ======
DJANGO_PORT = config('DJANGO_PORT', cast=int, default='8000')
DJANGO_PYTHON = Path(config('DJANGO_PYTHON'))
DJANGO_MANAGE = Path(config('DJANGO_MANAGE'))
DJANGO_WORKDIR = Path(config('DJANGO_WORKDIR'))
LOG_FILE = Path(config('LOG_FILE'))

LOG_DIR = os.path.dirname(LOG_FILE)
# =============================================================

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def is_port_open(port, host="127.0.0.1", timeout=1.0):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            return s.connect_ex((host, port)) == 0
        except Exception:
            return False


def start_wsl():
    """Quick harmless WSL call to ensure WSL is up (non-blocking)."""
    logging.info("Checking WSL status...")
    try:
        # don't use shell=True; keep it simple and short (timeout protects us)
        subprocess.run(["wsl", "echo", "WSL is up"], timeout=5, check=False)
        logging.info("WSL ping sent.")
    except Exception as e:
        logging.error(f"WSL ping error: {e}")


def is_django_running_by_process():
    """Return True if a python process is running manage.py (best-effort)."""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            name = proc.info.get('name') or ""
            cmdline = " ".join(proc.info.get('cmdline') or [])
            if "python" in name.lower() and "manage.py" in cmdline:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def start_django():
    """Start Django using the venv Python. Non-blocking."""
    logging.warning("Django not running — starting Django...")
    try:
        cmd = [DJANGO_PYTHON, DJANGO_MANAGE, "runserver", f"0.0.0.0:{DJANGO_PORT}"]
        # CREATE_NEW_PROCESS_GROUP lets it run independently on Windows
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(cmd, cwd=DJANGO_WORKDIR, creationflags=creationflags)
        logging.info("Django start command executed.")
    except Exception as e:
        logging.error(f"Failed to start Django: {e}")


def monitor_loop():
    logging.info("Monitor loop started.")
    running = True
    try:
        while running:
            try:
                start_wsl()
                # prefer checking the port first (fast)
                if not is_port_open(DJANGO_PORT):
                    logging.info("Port check: Django not listening.")
                    # as extra, verify via process presence
                    if not is_django_running_by_process():
                        start_django()
                    else:
                        logging.info("Process check suggests Django is running; port closed.")
                        # attempt to restart anyway
                        start_django()
                else:
                    logging.info("Django port is open; Django running normally.")
            except Exception as inner_e:
                logging.exception(f"Error during monitor pass: {inner_e}")
            # sleep but allow for interruption
            for _ in range(10):
                time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Monitor loop interrupted (e.g., Ctrl+C). Exiting.")
    except Exception as e:
        logging.exception(f"Monitor loop crashed: {e}")
    logging.info("Monitor loop exiting.")


if __name__ == "__main__":
    logging.info("Starting monitor script...")
    monitor_loop()
