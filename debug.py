import threading

import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import time
import socket
import psutil
import os
import logging

# === CONFIG ===
DJANGO_PORT = 8000

DJANGO_PYTHON = r"C:\Users\Ali\Desktop\TectoTrack\services\tecto-metadata-api\.venv\Scripts\python.exe"
DJANGO_MANAGE = r"C:\Users\Ali\Desktop\TectoTrack\services\tecto-metadata-api\manage.py"
DJANGO_WORKDIR = r"C:\Users\Ali\Desktop\TectoTrack\services\tecto-metadata-api"

DJANGO_COMMAND = [DJANGO_PYTHON, DJANGO_MANAGE, "runserver", f"0.0.0.0:{DJANGO_PORT}"]

DJANGO_PROCESS_NAME = "manage.py"  # for process check
LOG_FILE = r".\wsl_django_service.log"

# === Logging Setup ===
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def is_port_open(port):
    """Check if a port is listening (Django running)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

def start_wsl():
    """Run a harmless command to ensure WSL is loaded."""
    logging.info("Checking WSL status...")
    subprocess.run(["wsl", "echo", "WSL is up"], shell=True)
    logging.info("WSL ping sent.")

def is_django_running():
    """Check if Django process is running by process name."""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if proc.info['name'] and "python" in proc.info['name'].lower():
                if proc.info['cmdline'] and DJANGO_PROCESS_NAME in " ".join(proc.info['cmdline']):
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def start_django():
    """Start Django server."""
    logging.warning("Django is not running. Starting Django...")
    subprocess.Popen(DJANGO_COMMAND, cwd=DJANGO_WORKDIR)
    logging.info("Django start command executed.")

class WSLDjangoService(win32serviceutil.ServiceFramework):
    _svc_name_ = "WSLDjangoService"
    _svc_display_name_ = "WSL + Django Monitor Service"
    _svc_description_ = "Keeps WSL and Django running at all times."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        logging.info("Service stop requested.")
        self.running = False
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        logging.info("Service started.")
        servicemanager.LogInfoMsg("WSLDjangoService started.")

        # Run the main loop in a thread
        t = threading.Thread(target=self.main_loop)
        t.start()

        # Wait for stop signal
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

    def main_loop(self):
        while self.running:
            try:
                start_wsl()
                if not is_django_running() or not is_port_open(DJANGO_PORT):
                    start_django()
                else:
                    logging.info("Django is running normally.")
            except Exception as e:
                logging.error(f"Error in service loop: {e}")
            time.sleep(10)

if __name__ == '__main__':
    logging.info("DEBUG MODE: Starting loop")
    while True:
        try:
            start_wsl()
            if not is_django_running() or not is_port_open(DJANGO_PORT):
                start_django()
            else:
                logging.info("Django is running normally.")
        except Exception as e:
            logging.error(f"Error in debug loop: {e}")
        time.sleep(10)
