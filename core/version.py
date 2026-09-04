"""The single place the app's identity and version live.

Everything else -- the window, the settings About page, the updater, the
installer script and the CI workflow -- reads from here.
"""

__version__ = "1.0.3"

APP_NAME = "Neeko's Little Draft Assistant"
APP_SHORT_NAME = "Neeko Draft Assistant"
APP_ID = "NeekoDraftAssistant"
PUBLISHER = "Chris"

GITHUB_OWNER = "seraphicidal"
GITHUB_REPO = "neeko-draft-assistant"
GITHUB_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

# The installer asset a release must carry for the updater to offer it.
INSTALLER_SUFFIX = "-Setup.exe"


def version_tuple(text: str = __version__) -> tuple[int, int, int]:
    """Parse `1.2.3`, `v1.2.3` or `1.2.3-beta` into comparable numbers."""
    cleaned = text.strip().lstrip("vV").split("+")[0].split("-")[0]
    parts = cleaned.split(".")
    numbers = []
    for part in parts[:3]:
        try:
            numbers.append(int(part))
        except ValueError:
            numbers.append(0)
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)  # type: ignore[return-value]
