"""Start the engineering calculator window.

From the project folder:

    python main.py

You can also run ``python -m calculator``. Both do the same thing.
"""

import sys


def _load_main():
    try:
        from calculator.gui import main
    except ModuleNotFoundError as error:
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
