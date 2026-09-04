"""Neeko's Draft Assistant - auto accept, auto declare, auto chat.

    python main.py           (console attached, handy while debugging)
    pythonw main.py          (silent, what the launchers use)
"""

import sys

from ui.app import main

if __name__ == "__main__":
    sys.exit(main())
