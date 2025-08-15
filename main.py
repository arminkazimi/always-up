import os
import sys
import time
import socket
import logging
import threading
import subprocess

import psutil
import win32serviceutil
import win32service
import win32event
import servicemanager

# ====== CONFIG - change these to match your environment ======
DJANGO_PORT = 8000

DJANGO_PYTHON = r"C:\Users\Ali\Desktop\TectoTrack\services\tecto-metadata-api\.venv\Scripts\python.exe"
DJANGO_MANAGE = r"C:\Users\Ali\Desktop\TectoTrack\services\tecto-metadata-api\manage.py"
DJANGO_WORKDIR = r"C:\Users\Ali\Desktop\TectoTrack\services\tecto-metadata-api"

LOG_FILE = r"C:\Users\Ali\Desktop\TectoTrack\always-up\wsl_django_service.log"
LOG_DIR = os.path.dirname(LOG_FILE)
# =============================================================

# ensure log directory exists
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

class WSLDjangoService(win32serviceutil.ServiceFramework):
    _svc_name_ = "WSLDjangoService"
    _svc_display_name_ = "WSL + Django Monitor Service"
    _svc_description_ = "Keeps WSL and Django running at all times."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hStopEvent = win32event.CreateEvent(None, 0, 0, None)
        self.running = threading.Event()
        self.running.set()

    def SvcStop(self):
        logging.info("SvcStop called. Stopping service...")
        self.running.clear()
        win32event.SetEvent(self.hStopEvent)
        # tell SCM we're stopping
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

    def SvcDoRun(self):
        try:
            logging.info("SvcDoRun: service starting...")
            # tell SCM we're starting (optional but explicit)
            self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
            # Start monitor thread quickly -> so SvcDoRun won't block SCM
            t = threading.Thread(target=self.monitor_loop, name="MonitorThread", daemon=True)
            t.start()
            # tell SCM that service is running
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            servicemanager.LogInfoMsg("WSLDjangoService started.")
            logging.info("Service reported RUNNING to SCM.")
            # wait until stop event
            win32event.WaitForSingleObject(self.hStopEvent, win32event.INFINITE)
            logging.info("SvcDoRun: stop event signalled, exiting SvcDoRun.")
        except Exception as e:
            logging.exception(f"Unhandled exception in SvcDoRun: {e}")
            raise

    def monitor_loop(self):
        logging.info("Monitor loop started.")
        try:
            while self.running.is_set():
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
                # sleep but wake quickly if stopping
                for _ in range(10):
                    if not self.running.is_set():
                        break
                    time.sleep(1)
        except Exception as e:
            logging.exception(f"Monitor loop crashed: {e}")
        logging.info("Monitor loop exiting.")

if __name__ == "__main__":
    # allow a debug mode so you can test without installing
    if len(sys.argv) > 1 and sys.argv[1].lower() == "debug":
        logging.info("DEBUG MODE: running monitor loop directly (no service).")
        # run same loop as the service thread
        svc = WSLDjangoService(None)
        try:
            svc.monitor_loop()
        except KeyboardInterrupt:
            logging.info("DEBUG MODE: keyboard interrupt, exiting.")
    else:
        # normal service entry points: install / start / stop / remove / etc.
        win32serviceutil.HandleCommandLine(WSLDjangoService)
