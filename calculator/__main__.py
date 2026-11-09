"""Open the calculator with ``python -m calculator``."""

import sys


def _load_main():
    try:
        from .gui import main
    except ModuleNotFoundError as error:
        # gui.py imports tkinter. Give a direct hint when that module is missing.
        if error.name == "tkinter":
            sys.stderr.write(
                "Tkinter is required to open the window, and it is not installed.\n"
                "On Ubuntu, install it with:\n"
                "    sudo apt install python3-tk\n"
            )
            sys.exit(1)
        raise
    return main


if __name__ == "__main__":
    _load_main()()
