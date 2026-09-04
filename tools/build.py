"""Build the Windows app and its installer.

    python tools/build.py            executable + installer
    python tools/build.py --exe      executable only
    python tools/build.py --clean    remove build output first

The version comes from core/version.py and is handed to both PyInstaller and
Inno Setup, so it is never written down twice.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.version import APP_ID, APP_NAME, PUBLISHER, __version__  # noqa: E402

DIST = ROOT / "dist"
BUILD = ROOT / "build"
BUNDLE = DIST / APP_ID
SPEC = ROOT / "packaging" / "neeko.spec"
ISS = ROOT / "packaging" / "installer.iss"
VERSION_FILE = ROOT / "packaging" / "file_version.txt"

ISCC_CANDIDATES = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
]


def find_iscc() -> Path | None:
    found = shutil.which("iscc") or shutil.which("ISCC")
    if found:
        return Path(found)
    for candidate in ISCC_CANDIDATES:
        if candidate.parts and candidate.exists():
            return candidate
    return None


def write_version_resource() -> None:
    """The VERSIONINFO block Windows shows in the file properties dialog."""
    major, minor, patch = (int(part) for part in __version__.split(".")[:3])
    VERSION_FILE.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', {PUBLISHER!r}),
         StringStruct('FileDescription', {APP_NAME!r}),
         StringStruct('FileVersion', {__version__!r}),
         StringStruct('InternalName', {APP_ID!r}),
         StringStruct('OriginalFilename', {APP_ID + '.exe'!r}),
         StringStruct('ProductName', {APP_NAME!r}),
         StringStruct('ProductVersion', {__version__!r})])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
    )


def run(command: list[str], what: str) -> None:
    print(f"\n>>> {what}\n    {' '.join(command)}\n")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"{what} failed with exit code {result.returncode}")


def build_executable() -> Path:
    write_version_resource()
    run(
        [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm", "--distpath",
         str(DIST), "--workpath", str(BUILD)],
        "PyInstaller",
    )
    executable = BUNDLE / f"{APP_ID}.exe"
    if not executable.exists():
        raise SystemExit(f"PyInstaller did not produce {executable}")
    size = sum(path.stat().st_size for path in BUNDLE.rglob("*") if path.is_file())
    print(f"\n    built {executable}  ({size / 1024 / 1024:.0f} MB in the folder)")
    return executable


def build_installer() -> Path:
    iscc = find_iscc()
    if iscc is None:
        raise SystemExit(
            "Inno Setup was not found. Install it with:\n"
            "    winget install -e --id JRSoftware.InnoSetup"
        )
    run(
        [
            str(iscc),
            f"/DAppVersion={__version__}",
            f"/DSourceDir={BUNDLE}",
            f"/DOutputDir={DIST}",
            str(ISS),
        ],
        "Inno Setup",
    )
    installer = DIST / f"{APP_ID}-{__version__}-Setup.exe"
    if not installer.exists():
        raise SystemExit(f"Inno Setup did not produce {installer}")
    print(f"\n    built {installer}  ({installer.stat().st_size / 1024 / 1024:.1f} MB)")
    return installer


def main() -> int:
    arguments = set(sys.argv[1:])

    if "--clean" in arguments:
        for folder in (DIST, BUILD):
            shutil.rmtree(folder, ignore_errors=True)
        print("cleaned build output")

    print(f"Building {APP_NAME} {__version__}")
    build_executable()
    if "--exe" not in arguments:
        build_installer()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
