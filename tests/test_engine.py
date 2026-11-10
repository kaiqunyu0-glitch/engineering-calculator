"""Tests for the calculation engine.

These tests do not open a window. Run them from the project folder:

    pytest
"""

import ast
from pathlib import Path

import pytest

from calculator import Calculator, CalculatorError, format_result

PACKAGE = Path(__file__).resolve().parents[1] / "calculator"


@pytest.fixture
def calc() -> Calculator:
    return Calculator()


class TestArithmetic:
    def test_addition_subtraction_and_precedence(self, calc: Calculator) -> None:
        assert calc.evaluate("2 + 3 * 4") == 14
        assert calc.evaluate("(2 + 3) * 4") == 20
        assert calc.evaluate("10 - 3 - 2") == 5
        assert calc.evaluate("  8  /  2  ") == 4

    def test_unary_signs(self, calc: Calculator) -> None:
        assert calc.evaluate("-5 + 2") == -3
        assert calc.evaluate("2 * -3") == -6
        assert calc.evaluate("2 * (-3)") == -6
        assert calc.evaluate("-.5") == -0.5
        # Power binds more tightly than a leading minus, as in ordinary maths.
        assert calc.evaluate("-2^2") == -4
        assert calc.evaluate("(-2)^2") == 4

    def test_power_is_right_associative(self, calc: Calculator) -> None:
        assert calc.evaluate("2^10") == 1024
        assert calc.evaluate("2**10") == 1024
        assert calc.evaluate("2^3^2") == 512
        assert calc.evaluate("(2^3)^2") == 64
        assert calc.evaluate("(-2)^3") == -8

    def test_decimal_and_leading_zeros(self, calc: Calculator) -> None:
        assert calc.evaluate("007") == 7
        assert calc.evaluate("00.5") == 0.5
        assert calc.evaluate(".25 * 4") == 1

    def test_float_dust_is_rounded_on_the_final_result(self, calc: Calculator) -> None:
        # 0.1 + 0.2 is not exactly 0.3 in binary floating point. The engine
        # rounds the finished answer to 12 significant digits.
        assert calc.evaluate("0.1 + 0.2") == 0.3

    def test_unicode_operators_and_square(self, calc: Calculator) -> None:
        assert calc.evaluate("6×7") == 42
        assert calc.evaluate("8÷2") == 4
        assert calc.evaluate("5−3") == 2
        assert calc.evaluate("5²") == 25


class TestFunctions:
    def test_sqrt_square_reciprocal_and_abs(self, calc: Calculator) -> None:
        assert calc.evaluate("sqrt(49)") == 7
        assert calc.evaluate("sqrt(0)") == 0
        assert calc.evaluate("(3 + 1)^2") == 16
        assert calc.evaluate("1/(4)") == 0.25
        assert calc.evaluate("abs(-3)") == 3
        assert calc.evaluate("abs(-3.5)") == 3.5
        assert calc.evaluate("abs(0)") == 0

    def test_nth_root(self, calc: Calculator) -> None:
        assert calc.evaluate("nroot(8, 3)") == 2
        assert calc.evaluate("nroot(81, 4)") == 3
        assert calc.evaluate("nroot(-8, 3)") == -2
        assert calc.evaluate("nroot(0, 5)") == 0
        assert calc.evaluate("nroot(4, 0.5)") == 16

    def test_percent_applies_to_the_value_on_its_left(self, calc: Calculator) -> None:
        assert calc.evaluate("50%") == 0.5
        assert calc.evaluate("200%") == 2
        assert calc.evaluate("5+2%") == 5.02
        assert calc.evaluate("(5+2)%") == 0.07

    def test_factorial(self, calc: Calculator) -> None:
        assert calc.evaluate("0!") == 1
        assert calc.evaluate("6!") == 720
        assert calc.evaluate("(3+2)!") == 120
        assert calc.evaluate("factorial(5)") == 120
        assert calc.evaluate("fact(5.0)") == 120
        # A second ! means factorial of the factorial, not double factorial.
        assert calc.evaluate("3!!") == 720
        assert calc.evaluate("5!%") == 1.2

    def test_logs_and_exp(self, calc: Calculator) -> None:
        assert calc.evaluate("log(100)") == 2
        assert calc.evaluate("log10(1000)") == 3
        assert calc.evaluate("log(8, 2)") == 3
        assert calc.evaluate("log(81, 3)") == 4
        assert calc.evaluate("ln(e)") == 1
        assert calc.evaluate("exp(0)") == 1
        assert calc.evaluate("exp(1)") == pytest.approx(calc.evaluate("e"))

    def test_constants_and_implicit_multiplication(self, calc: Calculator) -> None:
        assert calc.evaluate("pi") == pytest.approx(3.141592653589793)
        assert calc.evaluate("PI") == pytest.approx(3.141592653589793)
        assert calc.evaluate("π*2") == pytest.approx(2 * 3.141592653589793)
        assert calc.evaluate("2pi") == pytest.approx(2 * 3.141592653589793)
        assert calc.evaluate("2(3+4)") == 14
        assert calc.evaluate("(2)(3)") == 6
        assert calc.evaluate("2*e") == pytest.approx(2 * 2.718281828459045)

    def test_large_exact_integer_power(self, calc: Calculator) -> None:
        assert calc.evaluate("2^10 + log(1000) + sqrt(81)") == 1036
        assert calc.evaluate("2^40") == 2**40


class TestTrigonometry:
    def test_degrees_are_the_default(self, calc: Calculator) -> None:
        assert calc.angle_mode == "DEG"
        assert calc.evaluate("sin(30)") == 0.5
        assert calc.evaluate("cos(60)") == 0.5
        assert calc.evaluate("tan(45)") == 1
        assert calc.evaluate("asin(0.5)") == 30
        assert calc.evaluate("acos(0.5)") == 60
        assert calc.evaluate("atan(1)") == 45
        assert calc.evaluate("arcsin(1)") == 90

    def test_radians(self, calc: Calculator) -> None:
        calc.set_angle_mode("rad")
        assert calc.angle_mode == "RAD"
        assert calc.evaluate("sin(pi/2)") == 1
        assert calc.evaluate("cos(0)") == 1
        assert calc.evaluate("asin(1)") == pytest.approx(calc.evaluate("pi/2"))
        assert calc.toggle_angle_mode() == "DEG"
        assert calc.evaluate("sin(30)") == 0.5

    def test_setting_the_attribute_uses_the_same_check(self, calc: Calculator) -> None:
        calc.angle_mode = "rad"
        assert calc.angle_mode == "RAD"
        with pytest.raises(CalculatorError, match="DEG or RAD"):
            calc.set_angle_mode("grad")

    def test_hyperbolic_functions_ignore_the_angle_mode(self, calc: Calculator) -> None:
        assert calc.evaluate("sinh(0)") == 0
        assert calc.evaluate("cosh(0)") == 1
        assert calc.evaluate("tanh(0)") == 0
        degrees = calc.evaluate("sinh(1)")
        calc.toggle_angle_mode()
        assert calc.evaluate("sinh(1)") == degrees

    def test_two_sin_forms_and_implicit_multiplication(self, calc: Calculator) -> None:
        assert calc.evaluate("SIN(30)") == 0.5
        assert calc.evaluate("2sin(30)") == 1


class TestAnsMemoryAndHistory:
    def test_ans_starts_at_zero_and_updates_after_success(self, calc: Calculator) -> None:
        assert calc.evaluate("Ans + 1") == 1
        assert calc.evaluate("2 + 2") == 4
        assert calc.evaluate("Ans * 3") == 12
        assert calc.ans == 12

    def test_failed_calculation_keeps_ans_and_history(self, calc: Calculator) -> None:
        calc.evaluate("10")
        with pytest.raises(CalculatorError):
            calc.evaluate("1/0")
        assert calc.ans == 10
        assert len(calc.history) == 1
        assert calc.history[0].expression == "10"
        assert calc.history[0].result == "10"

    def test_memory_buttons_are_engine_methods(self, calc: Calculator) -> None:
        calc.evaluate("10")
        assert calc.memory_add(calc.ans) == 10
        assert calc.memory_add(5) == 15
        assert calc.memory_subtract(3) == 12
        assert calc.memory_recall() == 12
        assert calc.memory == 12
        calc.memory_clear()
        assert calc.memory_recall() == 0

    def test_memory_rejects_non_numbers(self, calc: Calculator) -> None:
        with pytest.raises(CalculatorError):
            calc.memory_add("10")  # type: ignore[arg-type]

    def test_history_can_be_cleared_and_is_capped(self, calc: Calculator) -> None:
        calc.evaluate("1")
        calc.clear_history()
        assert calc.history == []
        for number in range(105):
            calc.evaluate(str(number))
        assert len(calc.history) == 100
        assert calc.history[0].expression == "5"
        assert calc.history[-1].expression == "104"

    def test_record_false_updates_ans_without_history(self, calc: Calculator) -> None:
        assert calc.evaluate("4", record=False) == 4
        assert calc.ans == 4
        assert calc.history == []


class TestScientificNotation:
    def test_exponent_notation(self, calc: Calculator) -> None:
        assert calc.evaluate("1.5E-3") == 0.0015
        assert calc.evaluate("1.5e+3") == 1500
        assert calc.evaluate("6.02e23") == pytest.approx(6.02e23)

    def test_unfinished_exponent_is_explained(self, calc: Calculator) -> None:
        with pytest.raises(CalculatorError, match="exponent"):
            calc.evaluate("2E")
        with pytest.raises(CalculatorError, match="Euler"):
            calc.evaluate("2e")
        with pytest.raises(CalculatorError, match="scientific notation"):
            calc.evaluate("E")


class TestErrors:
    @pytest.mark.parametrize(
        ("expression", "match"),
        [
            ("1/0", "divide by zero"),
            ("1/(0)", "divide by zero"),
            ("0^-1", "divide by zero"),
            ("sqrt(-1)", "Square root"),
            ("ln(0)", "positive"),
            ("ln(-2)", "positive"),
            ("log(-5)", "positive"),
            ("log(8, 1)", "base"),
            ("log(8, -2)", "base"),
            ("nroot(4, 0)", "cannot be zero"),
            ("nroot(-8, 2)", "Even roots"),
            ("(-8)^(1/3)", "nroot"),
            ("factorial(-1)", "whole numbers"),
            ("factorial(1.5)", "whole numbers"),
            ("factorial(1001)", "1000"),
            ("!", "needs a value"),
            ("tan(90)", "undefined"),
            ("asin(2)", "Inverse sine"),
            ("acos(2)", "Inverse cosine"),
            ("", "Enter an expression"),
            ("   ", "Enter an expression"),
            ("2+", "incomplete"),
            ("(", "missing"),
            (")", "extra"),
            ("1.2.3", "decimal point"),
            ("2//2", "integer division"),
            ("sin", "function"),
            ("foo", "Unknown name"),
            ("foo(1)", "Unknown function"),
            ("sqrt(4, 5)", "exactly 1"),
            ("log()", "1 or 2"),
            ("1, 2", "comma"),
            ("2^100000", "too large"),
            ("9^9^9", "too large"),
        ],
    )
    def test_friendly_errors(self, calc: Calculator, expression: str, match: str) -> None:
        with pytest.raises(CalculatorError, match=match):
            calc.evaluate(expression)

    def test_unexpected_character(self, calc: Calculator) -> None:
        with pytest.raises(CalculatorError, match="don't understand"):
            calc.evaluate("2 @ 3")

    def test_expression_length_limit(self, calc: Calculator) -> None:
        with pytest.raises(CalculatorError, match="too long"):
            calc.evaluate("1+" * 400 + "1")

    def test_non_string_input(self, calc: Calculator) -> None:
        with pytest.raises(CalculatorError, match="Enter an expression"):
            calc.evaluate(12)  # type: ignore[arg-type]


class TestSafety:
    @pytest.mark.parametrize(
        "expression",
        [
            "__import__('os')",
            "().__class__",
            "sin.__globals__",
            "(lambda: 1)()",
            "open('x')",
            "eval(1)",
            "[1, 2, 3]",
            "{1}",
            "1 if 1 else 0",
            "a:=1",
            "().__class__.__bases__",
        ],
    )
    def test_rejects_python_that_is_not_maths(self, calc: Calculator, expression: str) -> None:
        before = calc.ans
        with pytest.raises(CalculatorError):
            calc.evaluate(expression)
        assert calc.ans == before

    def test_sources_do_not_call_eval_exec_or_import(self) -> None:
        banned = {"eval", "exec", "__import__"}
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    assert node.func.id not in banned


class TestFormatting:
    def test_everyday_numbers(self) -> None:
        assert format_result(0) == "0"
        assert format_result(-0.0) == "0"
        assert format_result(5) == "5"
        assert format_result(2.0) == "2"
        assert format_result(0.1 + 0.2) == "0.3"
        assert format_result(1 / 4) == "0.25"

    def test_scientific_notation_for_extreme_magnitudes(self) -> None:
        assert format_result(1e13) == "1e+13"
        assert format_result(1.5e-8) == "1.5e-8"
        assert format_result(-1.5e-8) == "-1.5e-8"

    def test_large_integers_stay_exact(self) -> None:
        assert format_result(2**40) == str(2**40)

    def test_rejects_non_numbers(self) -> None:
        with pytest.raises(CalculatorError):
            format_result("4")  # type: ignore[arg-type]
        with pytest.raises(CalculatorError):
            format_result(float("inf"))
