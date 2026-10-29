
import ctypes
import sys

from ui.app import main


def _acquire_single_instance():
    if sys.platform != "win32":
        return True
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "NeekoDraftAssistant_SingleInstance_Mutex")
    if ctypes.windll.kernel32.GetLastError() == 183:
        hwnd = ctypes.windll.user32.FindWindowW(None, "Neeko's Little Draft Assistant")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        return None
    return mutex


if __name__ == "__main__":
    _mutex = _acquire_single_instance()
    if _mutex is None:
        sys.exit(0)
    sys.exit(main())
