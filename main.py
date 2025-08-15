import servicemanager
import win32service
import win32serviceutil
import win32event
import socket
import threading
import subprocess
import os
import time
import logging

# === CONFIG ===
DJANGO_PORT = 8000
DJANGO_PYTHON = r"C:\Users\Ali\Desktop\TectoTrack\services\tecto-metadata-api\.venv\Scripts\python.exe"
DJANGO_MANAGE = r"C:\Users\Ali\Desktop\TectoTrack\services\tecto-metadata-api\manage.py"
DJANGO_WORKDIR = r"C:\Users\Ali\Desktop\TectoTrack\services\tecto-metadata-api"

LOG_FILE = r"C:\Users\Ali\Desktop\TectoTrack\always-up\service.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

class WSLDjangoService(win32serviceutil.ServiceFramework):
    _svc_name_ = "WSLDjangoService"
    _svc_display_name_ = "WSL and Django Always-Up Service"
    _svc_description_ = "Keeps WSL and Django server running."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        logging.info("Stopping service...")
        self.running = False
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        logging.info("Service starting...")
        # Start monitoring in a background thread
        t = threading.Thread(target=self.monitor_loop)
        t.start()
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)

    def monitor_loop(self):
        while self.running:
            try:
                self.check_wsl()
                self.check_django()
            except Exception as e:
                logging.error(f"Error in monitor loop: {e}")
            time.sleep(10)

    def check_wsl(self):
        logging.info("Checking WSL status...")
        try:
            subprocess.run(["wsl", "echo", "ping"], timeout=5)
        except Exception as e:
            logging.error(f"WSL check error: {e}")

    def check_django(self):
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", DJANGO_PORT))
        sock.close()
        if result != 0:
            self.start_django()

    def start_django(self):
        logging.warning("Django is not running. Starting Django...")
        try:
            subprocess.Popen(
                [DJANGO_PYTHON, DJANGO_MANAGE, "runserver", f"0.0.0.0:{DJANGO_PORT}"],
                cwd=DJANGO_WORKDIR
            )
            logging.info("Django start command executed.")
        except Exception as e:
            logging.error(f"Failed to start Django: {e}")

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(WSLDjangoService)
