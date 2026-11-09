"""Desktop engineering calculator.

The maths engine does not need a window, so you can try it from a shell::

    from calculator import Calculator
    print(Calculator().evaluate("sin(30)"))

Open the window with ``python main.py`` or ``python -m calculator``.
"""

from .engine import Calculator, CalculatorError, HistoryEntry, format_result

__all__ = [
    "Calculator",
    "CalculatorError",
    "HistoryEntry",
    "format_result",
]

__version__ = "1.0.0"
