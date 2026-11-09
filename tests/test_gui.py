"""Tests for window wiring.

The number rules live in test_engine.py. These tests check that the keys,
the keyboard, history, and memory talk to that engine. They need Tk and a
display; if either is missing, the window tests are skipped.
"""

from __future__ import annotations

import pytest

try:
    import tkinter as tk
    from calculator.gui import CalculatorApp, reciprocal_text, square_text
except ModuleNotFoundError as error:
    if error.name != "tkinter":
        raise
    pytest.skip("Tkinter is not installed", allow_module_level=True)


class TestExpressionEditing:
    def test_square_wraps_a_sum_and_uses_ans_when_empty(self) -> None:
        assert square_text("") == "Ans^2"
        assert square_text("5") == "5^2"
        assert square_text("pi") == "pi^2"
        assert square_text("1.5E3") == "1.5E3^2"
        assert square_text("2+3") == "(2+3)^2"

    def test_reciprocal_wraps_the_whole_expression(self) -> None:
        assert reciprocal_text("") == "1/("
        assert reciprocal_text("4") == "1/(4)"
        assert reciprocal_text("2+3") == "1/(2+3)"


@pytest.fixture
def app():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"No display available: {error}")
    root.geometry("1040x720+40+40")
    application = CalculatorApp(root)
    # Map the window. Key events are ignored until Tk has processed it.
    root.update()
    yield application
    root.destroy()


class TestWindow:
    def test_window_opens(self, app: CalculatorApp) -> None:
        app.root.deiconify()
        app.root.update()
        assert app.root.winfo_exists()
        assert app.root.title() == "Engineering Calculator"
        assert app.root.winfo_width() > 200
        assert app.root.winfo_height() > 200
        assert app.result_text() == "0"
        assert app.engine.angle_mode == "DEG"

    def test_buttons_evaluate_and_clear(self, app: CalculatorApp) -> None:
        app.insert_text("2+2")
        app.buttons["="].invoke()
        assert app.result_text() == "4"
        assert app.engine.ans == 4

        app.buttons["C"].invoke()
        assert app.expression.get() == ""
        assert app.result_text() == "0"
        # Clear resets the display, not the previous answer.
        assert app.engine.ans == 4
        app.insert_text("Ans+1")
        app.evaluate_current()
        assert app.result_text() == "5"

    def test_backspace_and_function_keys(self, app: CalculatorApp) -> None:
        app.buttons["sin"].invoke()
        assert app.expression.get() == "sin("
        app.insert_text("30)")
        app.buttons["⌫"].invoke()
        assert app.expression.get() == "sin(30"
        app.insert_text(")")
        app.buttons["="].invoke()
        assert app.result_text() == "0.5"

    def test_square_reciprocal_and_nth_root_keys(self, app: CalculatorApp) -> None:
        app.insert_text("2+3")
        app.buttons["x²"].invoke()
        assert app.expression.get() == "(2+3)^2"
        app.buttons["="].invoke()
        assert app.result_text() == "25"

        app.clear_expression()
        app.insert_text("4")
        app.buttons["1/x"].invoke()
        assert app.expression.get() == "1/(4)"
        app.buttons["="].invoke()
        assert app.result_text() == "0.25"

        app.clear_expression()
        app.buttons["ⁿ√"].invoke()
        app.insert_text("8, 3)")
        app.buttons["="].invoke()
        assert app.result_text() == "2"

    def test_scientific_notation_key(self, app: CalculatorApp) -> None:
        app.insert_text("1.5")
        app.buttons["EXP"].invoke()
        app.insert_text("-3")
        assert app.expression.get() == "1.5E-3"
        app.evaluate_current()
        assert app.result_text() == "0.0015"

    def test_angle_toggle_changes_sine(self, app: CalculatorApp) -> None:
        app.insert_text("sin(30)")
        app.evaluate_current()
        assert app.result_text() == "0.5"
        app.buttons["DEG"].invoke()
        assert app.engine.angle_mode == "RAD"
        assert app.angle_badge.cget("text") == "RAD"
        app.evaluate_current()
        assert app.result_text() != "0.5"
        app.set_angle("DEG")
        assert app.engine.angle_mode == "DEG"

    def test_memory_keys(self, app: CalculatorApp) -> None:
        app.insert_text("10")
        app.evaluate_current()
        app.buttons["M+"].invoke()
        app.buttons["M+"].invoke()
        assert app.engine.memory == 20
        assert app.memory_badge.cget("text") == "M"

        app.clear_expression()
        app.buttons["MR"].invoke()
        assert app.expression.get() == "20"
        app.buttons["M-"].invoke()
        assert app.engine.memory == 0
        assert app.memory_badge.cget("text") == ""

        app.buttons["M+"].invoke()
        assert app.engine.memory == 20
        app.buttons["MC"].invoke()
        assert app.engine.memory == 0

    def test_history_loads_an_older_expression(self, app: CalculatorApp) -> None:
        app.insert_text("1+1")
        app.evaluate_current()
        app.clear_expression()
        app.insert_text("3*3")
        app.evaluate_current()
        assert app.history_list.size() == 2

        app.history_list.selection_set(0)
        app.on_history_select()
        assert app.expression.get() == "1+1"
        assert app.result_text() == "2"

        app.clear_history()
        assert app.history_list.size() == 0

    def test_division_by_zero_is_shown_and_does_not_crash(self, app: CalculatorApp) -> None:
        app.insert_text("1/0")
        app.evaluate_current()
        assert "divide by zero" in app.result_text()
        assert app.engine.ans == 0
        # The window is still usable after the error.
        app.clear_expression()
        app.insert_text("6*7")
        app.entry.focus_set()
        app.entry.event_generate("=")
        app.root.update()
        assert app.expression.get() == "6*7"
        assert app.result_text() == "42"

    def test_escape_clears(self, app: CalculatorApp) -> None:
        app.insert_text("123")
        app.entry.focus_set()
        app.entry.event_generate("<Escape>")
        app.root.update()
        assert app.expression.get() == ""
        assert app.result_text() == "0"
