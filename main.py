
import ctypes
from pathlib import Path
import sys

from core.version import APP_USER_MODEL_ID
from ui.app import main


def _set_app_id() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        except Exception:
            pass


def _sync_tray_cache() -> None:
    if sys.platform != "win32":
        return
    try:
        import winreg

        png_path = Path(__file__).resolve().parent / "assets" / "icon.png"
        if getattr(sys, "frozen", False):
            png_path = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "assets" / "icon.png"
        if not png_path.exists():
            return
        data = png_path.read_bytes()
        key_path = r"Control Panel\NotifyIconSettings"
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE
        ) as parent:
            count, _, _ = winreg.QueryInfoKey(parent)
            for index in range(count):
                try:
                    sub_name = winreg.EnumKey(parent, index)
                    with winreg.OpenKey(
                        parent, sub_name, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE
                    ) as sub:
                        exe, _ = winreg.QueryValueEx(sub, "ExecutablePath")
                        if "neekodraftassistant" in str(exe).lower():
                            winreg.SetValueEx(sub, "IconSnapshot", 0, winreg.REG_BINARY, data)
                except OSError:
                    continue
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass


def _acquire_single_instance():
    if sys.platform != "win32":
        return True
    _set_app_id()
    _sync_tray_cache()
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
