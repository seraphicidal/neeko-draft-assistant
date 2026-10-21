
__version__ = "1.0.5"

APP_NAME = "Neeko's Little Draft Assistant"
APP_SHORT_NAME = "Neeko Draft Assistant"
APP_ID = "NeekoDraftAssistant"
PUBLISHER = "Chris"

GITHUB_OWNER = "seraphicidal"
GITHUB_REPO = "neeko-draft-assistant"
GITHUB_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

INSTALLER_SUFFIX = "-Setup.exe"


def version_tuple(text: str = __version__) -> tuple[int, int, int]:
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
    return tuple(numbers)
