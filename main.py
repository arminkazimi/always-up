import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import time
import socket
import psutil
import os


DJANGO_PORT = 8000
DJANGO_COMMAND = r"python C:\path\to\manage.py runserver 0.0.0.0:8000"
DJANGO_PROCESS_NAME = "manage.py"  # for process check


def is_port_open(port):
    """Check if a port is listening (Django running)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_wsl():
    """Run a harmless command to ensure WSL is loaded."""
    subprocess.run(["wsl", "echo", "WSL is up"], shell=True)


def is_django_running():
    """Check if Django process is running by process name."""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if "python" in proc.info['name'].lower() and DJANGO_PROCESS_NAME in " ".join(proc.info['cmdline']):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def start_django():
    """Start Django server."""
    subprocess.Popen(DJANGO_COMMAND, shell=True, cwd=os.path.dirname(DJANGO_COMMAND))


class WSLDjangoService(win32serviceutil.ServiceFramework):
    _svc_name_ = "WSLDjangoService"
    _svc_display_name_ = "WSL + Django Monitor Service"
    _svc_description_ = "Keeps WSL and Django running at all times."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        self.running = False
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("WSLDjangoService started.")
        while self.running:
            try:
                # Keep WSL alive
                start_wsl()

                # Ensure Django is running
                if not is_django_running() or not is_port_open(DJANGO_PORT):
                    start_django()

            except Exception as e:
                servicemanager.LogErrorMsg(str(e))

            time.sleep(10)  # Check every 10 seconds


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(WSLDjangoService)
