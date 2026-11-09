"""Turn a calculator expression into a number, safely.

A calculator is often a student's first reason to reach for Python's eval
function. That is a bad fit here: eval runs whatever Python code it is
given, not just arithmetic. This module never calls eval.

An expression goes through five steps:

1. Replace a few look-alike characters (π, ×, ÷, ²) with plain text.
2. Split the text into tokens: numbers, names, operators, parentheses.
3. Rewrite calculator-only syntax into ordinary maths Python already
   understands. ``^`` becomes ``**``, ``5!`` becomes ``factorial(5)``,
   ``50%`` becomes ``percent(50)``, and ``2π`` gains a multiplication sign.
4. Parse the rewritten text into an abstract syntax tree. Parsing does
   not run the expression.
5. Walk that tree and evaluate only the nodes listed below. Anything else
   becomes a CalculatorError with a short message for the window.

Allowed pieces:

* numbers, including scientific notation such as ``1.5E-3``
* the names ``pi``, ``e``, and ``Ans``
* ``+  -  *  /  ^`` and parentheses
* the functions in ``Calculator._build_functions``

The calculator keeps 12 significant digits for non-integer results. That is
why ``0.1 + 0.2`` comes back as ``0.3`` instead of a long binary fraction.
Integers, including factorials, stay exact.
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass

# A factorial of 1000 is large, but Python builds it quickly. Beyond that
# the number of digits stops being useful on a desktop calculator.
MAX_FACTORIAL = 1000

# Stops a pasted page of text from tying up the parser.
MAX_EXPRESSION_LENGTH = 500

# 2^(2^(2^...)) can ask Python for an integer with millions of digits.
# A few thousand digits is already more than the display can show usefully.
MAX_RESULT_DIGITS = 5000

MAX_HISTORY = 100

# The tree walk is recursive. Stay well below Python's own recursion limit
# so a deeply nested expression still gets a readable error.
MAX_TREE_DEPTH = 100

# Names that are values, not function calls. ``pi(2)`` means ``pi * (2)``.
# ``sin(2)`` stays a function call.
_CONSTANTS = {"pi", "e", "ans"}

_NUMBER_RE = re.compile(r"(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?")
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Characters people paste from other apps. Each one becomes plain text
# before tokenization, so the rest of the engine only sees ASCII.
_CHAR_MAP = str.maketrans(
    {
        "π": "pi",
        "×": "*",
        "÷": "/",
        "−": "-",
        "–": "-",
        "—": "-",
        "²": "^2",
    }
)


class CalculatorError(Exception):
    """A problem the person using the calculator can fix.

    The message is written to be shown directly in the window.
    """


@dataclass(frozen=True)
class HistoryEntry:
    """One successful calculation, in the form the window displays."""

    expression: str
    result: str


class Token:
    """One piece of an expression.

    ``kind`` is a short label such as ``NUM`` or ``OP``. ``value`` is the
    text that piece came from, for example ``"sin"`` or ``"+"``.
    """

    __slots__ = ("kind", "value")

    def __init__(self, kind: str, value: str) -> None:
        self.kind = kind
        self.value = value

    def __repr__(self) -> str:
        return f"Token({self.kind!r}, {self.value!r})"


def format_result(value: int | float) -> str:
    """Format a number the way the display and the history list show it.

    Integers are printed in full, so a factorial is not rounded. Other
    numbers use 12 significant digits. Very large and very small numbers
    switch to scientific notation, for example ``1.5e-8``.
    """

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalculatorError("Result is not a real number.")
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise CalculatorError("Result is not a real number.")
    if value == 0:
        return "0"

    magnitude = abs(value)
    if magnitude >= 1e12 or magnitude < 1e-6:
        return _format_scientific(value)
    return f"{value:.12g}"


def _format_scientific(value: float) -> str:
    """Print ``1.50e-03`` style numbers as ``1.5e-3``."""

    mantissa, exponent = f"{value:.10e}".split("e")
    mantissa = mantissa.rstrip("0").rstrip(".")
    exponent_value = int(exponent)
    sign = "+" if exponent_value >= 0 else "-"
    return f"{mantissa}e{sign}{abs(exponent_value)}"


def _is_real_number(value: object) -> bool:
    # bool is a subclass of int, and True / False are not calculator values.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_real(value: object) -> int | float:
    if not _is_real_number(value):
        raise CalculatorError("Result is not a real number.")
    if isinstance(value, float) and not math.isfinite(value):
        raise CalculatorError("That number is too large to calculate.")
    return value


def _round_result(value: int | float) -> int | float:
    """Round a final answer to the precision the display promises.

    Integers stay exact. A float that lands on a whole number within the
    safe integer range (where every integer has an exact float) is stored
    as an int, so ``10 / 2`` is ``5`` rather than ``5.0``.
    """

    if isinstance(value, int):
        return value
    rounded = float(f"{value:.12g}")
    if math.isfinite(rounded) and rounded.is_integer() and abs(rounded) < 10**15:
        return int(rounded)
    return rounded


def _is_constant(name: str) -> bool:
    return name.lower() in _CONSTANTS


def _arity_message(name: str, minimum: int, maximum: int) -> str:
    if minimum == maximum:
        noun = "argument" if minimum == 1 else "arguments"
        return f"{name}() takes exactly {minimum} {noun}."
    return f"{name}() takes {minimum} or {maximum} arguments."


def _normalize_integer_literal(lexeme: str) -> str:
    """Turn ``007`` into ``7``.

    Python rejects a leading zero on an integer. Decimals and scientific
    notation, such as ``0.5`` and ``1.2E3``, are left as written.
    """

    if re.fullmatch(r"0\d+", lexeme):
        return lexeme.lstrip("0") or "0"
    return lexeme


def _tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    length = len(source)

    while index < length:
        char = source[index]
        if char.isspace():
            index += 1
            continue

        starts_number = char.isdigit() or (
            char == "." and index + 1 < length and source[index + 1].isdigit()
        )
        if starts_number:
            match = _NUMBER_RE.match(source, index)
            if match is None:
                raise CalculatorError("That number looks incomplete.")
            tokens.append(Token("NUM", _normalize_integer_literal(match.group())))
            index = match.end()
            continue

        if char == ".":
            raise CalculatorError("That decimal point needs digits, for example 0.5.")

        name_match = _NAME_RE.match(source, index)
        if name_match is not None:
            tokens.append(Token("NAME", name_match.group()))
            index = name_match.end()
            continue

        if char == "*" and index + 1 < length and source[index + 1] == "*":
            tokens.append(Token("OP", "**"))
            index += 2
            continue

        if char == "/" and index + 1 < length and source[index + 1] == "/":
            raise CalculatorError(
                "Use / for division. This calculator does not do integer division."
            )

        if char in "+-*/^":
            tokens.append(Token("OP", char))
            index += 1
            continue
        if char == "(":
            tokens.append(Token("LP", "("))
            index += 1
            continue
        if char == ")":
            tokens.append(Token("RP", ")"))
            index += 1
            continue
        if char == ",":
            tokens.append(Token("COMMA", ","))
            index += 1
            continue
        if char == "!":
            tokens.append(Token("FACT", "!"))
            index += 1
            continue
        if char == "%":
            tokens.append(Token("PCT", "%"))
            index += 1
            continue
        if char == "√":
            raise CalculatorError(
                "For a square root, write sqrt(x). For an nth root, write nroot(x, n)."
            )

        raise CalculatorError(f"I don't understand the character {char!r}.")

    return tokens


def _check_parentheses(tokens: list[Token]) -> None:
    depth = 0
    for token in tokens:
        if token.kind == "LP":
            depth += 1
        elif token.kind == "RP":
            depth -= 1
            if depth < 0:
                raise CalculatorError('Parentheses are mismatched. There is an extra ")".')
    if depth > 0:
        raise CalculatorError('Parentheses are mismatched. There is a missing ")".')


def _validate_tokens(tokens: list[Token]) -> None:
    """Catch mistakes that are easier to explain before parsing.

    Scientific notation is the awkward one. ``1.5E-3`` is a single number,
    but a bare ``E`` or a trailing ``2e`` is not. ``e`` by itself is
    Euler's number, so ``2*e`` is multiplication and ``2e`` is treated as
    an unfinished exponent instead of guessing.
    """

    _check_parentheses(tokens)
    for index, token in enumerate(tokens):
        previous = tokens[index - 1] if index else None
        if (
            previous is not None
            and previous.kind == "NUM"
            and token.kind == "NUM"
            and token.value.startswith(".")
        ):
            raise CalculatorError("That number has an extra decimal point.")

        if token.kind != "NAME" or token.value not in {"e", "E"}:
            continue

        if previous is not None and previous.kind == "NUM":
            raise CalculatorError(
                "Add an exponent after e, for example 2e3. "
                "To multiply by Euler's number, write 2*e."
            )
        if token.value == "E":
            raise CalculatorError(
                "E is for scientific notation, like 1.5E3. For Euler's number, use e."
            )


def _pop_operand(output: list[Token], operator_name: str) -> list[Token]:
    """Take the value a postfix operator applies to, off the end of ``output``.

    ``!`` and ``%`` bind to the value directly on their left. ``3!`` uses
    ``3``, ``(2+3)!`` uses the parentheses, and ``sin(30)!`` uses the call.
    A constant before parentheses is multiplication, not a call, so
    ``pi(2)!`` is ``pi * (2!)``.
    """

    if not output:
        raise CalculatorError(f"{operator_name} needs a value before it.")

    if output[-1].kind == "RP":
        depth = 0
        for index in range(len(output) - 1, -1, -1):
            if output[index].kind == "RP":
                depth += 1
            elif output[index].kind == "LP":
                depth -= 1
                if depth == 0:
                    start = index
                    if (
                        start > 0
                        and output[start - 1].kind == "NAME"
                        and not _is_constant(output[start - 1].value)
                    ):
                        start -= 1
                    operand = output[start:]
                    del output[start:]
                    return operand
        raise CalculatorError('Parentheses are mismatched. There is an extra ")".')

    if output[-1].kind in {"NUM", "NAME"}:
        return [output.pop()]

    raise CalculatorError(f"{operator_name} needs a value before it.")


def _rewrite_postfix(
    tokens: list[Token],
    kind: str,
    function_name: str,
    operator_name: str,
) -> list[Token]:
    """Replace a postfix operator with a function call.

    ``5!`` becomes ``factorial(5)``. Doing ``!`` before ``%`` means ``5!%``
    is "5 factorial, then percent", which matches reading left to right.
    ``3!!`` is factorial of factorial, not the double-factorial function.
    """

    output: list[Token] = []
    for token in tokens:
        if token.kind != kind:
            output.append(token)
            continue
        operand = _pop_operand(output, operator_name)
        output.append(Token("NAME", function_name))
        output.append(Token("LP", "("))
        output.extend(operand)
        output.append(Token("RP", ")"))
    return output


def _insert_implicit_multiplication(tokens: list[Token]) -> list[Token]:
    """Insert ``*`` where maths writes two values next to each other.

    ``2pi`` becomes ``2*pi``, ``2(3+4)`` becomes ``2*(3+4)``, and
    ``(2)(3)`` becomes ``(2)*(3)``. A function name followed by ``(`` is
    left alone so ``sin(30)`` stays a call.
    """

    if not tokens:
        return []

    result = [tokens[0]]
    for token in tokens[1:]:
        previous = result[-1]
        ends_value = previous.kind in {"NUM", "NAME", "RP"}
        starts_value = token.kind in {"NUM", "NAME", "LP"}
        if ends_value and starts_value:
            is_call = (
                previous.kind == "NAME"
                and token.kind == "LP"
                and not _is_constant(previous.value)
            )
            if not is_call:
                result.append(Token("OP", "*"))
        result.append(token)
    return result


def _render(tokens: list[Token]) -> str:
    pieces: list[str] = []
    for token in tokens:
        # Both ^ and ** are power. The parser only knows **.
        if token.kind == "OP" and token.value == "^":
            pieces.append("**")
        else:
            pieces.append(token.value)
    return "".join(pieces)


def _rewrite_expression(expression: str) -> str:
    """Turn calculator text into a restricted Python expression string."""

    tokens = _tokenize(expression.translate(_CHAR_MAP))
    if not tokens:
        raise CalculatorError("Enter an expression to evaluate.")
    _validate_tokens(tokens)
    tokens = _rewrite_postfix(tokens, "FACT", "factorial", "Factorial")
    tokens = _rewrite_postfix(tokens, "PCT", "percent", "Percent")
    tokens = _insert_implicit_multiplication(tokens)
    return _render(tokens)


class Calculator:
    """State for Ans, memory, angle mode, and the history list.

    Create one calculator and call :meth:`evaluate` for each expression.
    The window in ``calculator.gui`` holds a single instance. Tests can
    use the engine on its own, with no display.
    """

    def __init__(self) -> None:
        self.ans: int | float = 0
        self.history: list[HistoryEntry] = []
        self._memory: int | float = 0
        self._angle_mode = "DEG"
        self._functions = self._build_functions()

    def _build_functions(self) -> dict:
        """Map a lowercase function name to ``(function, min args, max args)``."""

        return {
            "sqrt": (self._sqrt, 1, 1),
            "nroot": (self._nroot, 2, 2),
            "abs": (self._absolute, 1, 1),
            "factorial": (self._factorial, 1, 1),
            "fact": (self._factorial, 1, 1),
            "percent": (self._percent, 1, 1),
            "sin": (self._sin, 1, 1),
            "cos": (self._cos, 1, 1),
            "tan": (self._tan, 1, 1),
            "asin": (self._asin, 1, 1),
            "acos": (self._acos, 1, 1),
            "atan": (self._atan, 1, 1),
            "arcsin": (self._asin, 1, 1),
            "arccos": (self._acos, 1, 1),
            "arctan": (self._atan, 1, 1),
            "sinh": (self._sinh, 1, 1),
            "cosh": (self._cosh, 1, 1),
            "tanh": (self._tanh, 1, 1),
            "log": (self._log, 1, 2),
            "log10": (self._log10, 1, 1),
            "ln": (self._ln, 1, 1),
            "exp": (self._exp, 1, 1),
        }

    @property
    def angle_mode(self) -> str:
        """``DEG`` or ``RAD``. This affects sin, cos, tan and their inverses."""

        return self._angle_mode

    @angle_mode.setter
    def angle_mode(self, mode: str) -> None:
        self.set_angle_mode(mode)

    def set_angle_mode(self, mode: str) -> str:
        if not isinstance(mode, str):
            raise CalculatorError("Angle mode must be DEG or RAD.")
        normalized = mode.strip().upper()
        if normalized not in {"DEG", "RAD"}:
            raise CalculatorError("Angle mode must be DEG or RAD.")
        self._angle_mode = normalized
        return self._angle_mode

    def toggle_angle_mode(self) -> str:
        """Switch between degrees and radians. Returns the new mode."""

        return self.set_angle_mode("RAD" if self._angle_mode == "DEG" else "DEG")

    @property
    def memory(self) -> int | float:
        return self._memory

    def memory_recall(self) -> int | float:
        return self._memory

    def memory_clear(self) -> None:
        self._memory = 0

    def memory_add(self, value: int | float) -> int | float:
        number = _require_real(value)
        self._memory = _require_real(self._memory + number)
        return self._memory

    def memory_subtract(self, value: int | float) -> int | float:
        number = _require_real(value)
        self._memory = _require_real(self._memory - number)
        return self._memory

    def clear_history(self) -> None:
        self.history.clear()

    def evaluate(self, expression: str, *, record: bool = True) -> int | float:
        """Evaluate ``expression`` and store the answer in :attr:`ans`.

        On success the result is appended to :attr:`history` when ``record``
        is true. A CalculatorError leaves Ans and the history unchanged.
        """

        if not isinstance(expression, str):
            raise CalculatorError("Enter an expression to evaluate.")
        text = expression.strip()
        if not text:
            raise CalculatorError("Enter an expression to evaluate.")
        if len(text) > MAX_EXPRESSION_LENGTH:
            raise CalculatorError(
                f"That expression is too long. The limit is {MAX_EXPRESSION_LENGTH} characters."
            )

        rewritten = _rewrite_expression(text)
        try:
            tree = ast.parse(rewritten, mode="eval")
        except SyntaxError:
            raise CalculatorError(
                "That expression looks incomplete or mistyped. "
                "Check parentheses and operators."
            ) from None

        try:
            value = self._eval_node(tree.body, 0)
        except CalculatorError:
            raise
        except ZeroDivisionError:
            raise CalculatorError("Cannot divide by zero.") from None
        except OverflowError:
            raise CalculatorError("That number is too large to calculate.") from None

        value = _round_result(_require_real(value))
        self.ans = value
        if record:
            self.history.append(HistoryEntry(text, format_result(value)))
            extra = len(self.history) - MAX_HISTORY
            if extra > 0:
                del self.history[:extra]
        return value

    def _eval_node(self, node: ast.AST, depth: int) -> int | float:
        if depth > MAX_TREE_DEPTH:
            raise CalculatorError("That expression is nested too deeply.")

        if isinstance(node, ast.Constant):
            if _is_real_number(node.value):
                return node.value
            raise CalculatorError("Only real numbers are allowed.")

        if isinstance(node, ast.Name):
            return self._lookup_name(node.id)

        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, depth + 1)
            if isinstance(node.op, ast.UAdd):
                return operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise CalculatorError("That operator is not supported.")

        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, depth + 1)
            right = self._eval_node(node.right, depth + 1)
            return self._eval_binop(node.op, left, right)

        if isinstance(node, ast.Call):
            return self._eval_call(node, depth)

        if isinstance(node, ast.Tuple):
            raise CalculatorError(
                "Unexpected comma. Commas belong inside functions, "
                "like nroot(8, 3) or log(8, 2)."
            )

        # Attribute access, subscripts, lambdas, comparisons, and similar
        # Python syntax are rejected here on purpose.
        raise CalculatorError("That expression is not supported.")

    def _lookup_name(self, name: str) -> int | float:
        lowered = name.lower()
        if lowered == "pi":
            return math.pi
        if lowered == "e":
            return math.e
        if lowered == "ans":
            return _require_real(self.ans)
        if lowered in self._functions:
            raise CalculatorError(f"{lowered} is a function. Write {lowered}(...) to call it.")
        raise CalculatorError(f"Unknown name {name!r}.")

    def _eval_binop(self, op: ast.operator, left: int | float, right: int | float) -> int | float:
        if isinstance(op, ast.Add):
            return _require_real(left + right)
        if isinstance(op, ast.Sub):
            return _require_real(left - right)
        if isinstance(op, ast.Mult):
            return _require_real(left * right)
        if isinstance(op, ast.Div):
            try:
                return _require_real(left / right)
            except ZeroDivisionError:
                raise CalculatorError("Cannot divide by zero.") from None
        if isinstance(op, ast.Pow):
            return self._safe_pow(left, right)
        # Modulo, floor division, and bitwise operators are not calculator keys.
        raise CalculatorError("That operator is not supported.")

    def _eval_call(self, node: ast.Call, depth: int) -> int | float:
        if not isinstance(node.func, ast.Name):
            raise CalculatorError("Only simple function names can be called.")
        if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
            raise CalculatorError("That expression is not supported.")

        name = node.func.id.lower()
        spec = self._functions.get(name)
        if spec is None:
            raise CalculatorError(f"Unknown function {node.func.id!r}.")

        function, minimum, maximum = spec
        count = len(node.args)
        if count < minimum or count > maximum:
            raise CalculatorError(_arity_message(name, minimum, maximum))

        arguments = [_require_real(self._eval_node(arg, depth + 1)) for arg in node.args]
        return _require_real(function(*arguments))

    def _safe_pow(self, base: int | float, exponent: int | float) -> int | float:
        """Power that stays in the real numbers and refuses huge results.

        ``^`` groups to the right, same as mathematics and Python: ``2^3^2``
        is ``2^(3^2)``, which is 512, not ``(2^3)^2``.

        A negative number to a fractional power is not a real number in this
        calculator. Odd roots of negatives are available through ``nroot``.
        """

        base = _require_real(base)
        exponent = _require_real(exponent)
        if isinstance(exponent, float) and exponent.is_integer() and abs(exponent) < 1e15:
            exponent = int(exponent)

        if base < 0 and not isinstance(exponent, int):
            raise CalculatorError(
                "Raising a negative number to that power is not a real number. "
                "For an odd root, use nroot(x, n)."
            )

        if isinstance(exponent, int) and exponent > 0 and abs(base) > 1:
            try:
                digits = math.log10(abs(base)) * exponent
            except (OverflowError, ValueError):
                raise CalculatorError("That number is too large to calculate.") from None
            if digits > MAX_RESULT_DIGITS:
                raise CalculatorError("That number is too large to calculate.")

        try:
            result = base**exponent
        except OverflowError:
            raise CalculatorError("That number is too large to calculate.") from None
        except ZeroDivisionError:
            raise CalculatorError("Cannot divide by zero.") from None

        if isinstance(result, complex):
            raise CalculatorError(
                "Raising a negative number to that power is not a real number. "
                "For an odd root, use nroot(x, n)."
            )
        return _require_real(result)

    def _to_radians(self, angle: int | float) -> float:
        if self._angle_mode == "DEG":
            return math.radians(angle)
        return float(angle)

    def _from_radians(self, angle: float) -> float:
        if self._angle_mode == "DEG":
            return math.degrees(angle)
        return angle

    def _tangent_undefined(self, angle: int | float, radians: float) -> bool:
        if self._angle_mode == "DEG":
            # Tangent is undefined at 90, 270, -90, and so on.
            distance = (angle - 90) % 180
            return distance < 1e-9 or distance > 180 - 1e-9
        return abs(math.cos(radians)) < 1e-12

    def _sin(self, angle: int | float) -> float:
        return math.sin(self._to_radians(angle))

    def _cos(self, angle: int | float) -> float:
        return math.cos(self._to_radians(angle))

    def _tan(self, angle: int | float) -> float:
        radians = self._to_radians(angle)
        if self._tangent_undefined(angle, radians):
            raise CalculatorError("Tangent is undefined at that angle.")
        return math.tan(radians)

    def _asin(self, value: int | float) -> float:
        if value < -1 or value > 1:
            raise CalculatorError("Inverse sine is only defined for values from -1 to 1.")
        return self._from_radians(math.asin(value))

    def _acos(self, value: int | float) -> float:
        if value < -1 or value > 1:
            raise CalculatorError("Inverse cosine is only defined for values from -1 to 1.")
        return self._from_radians(math.acos(value))

    def _atan(self, value: int | float) -> float:
        return self._from_radians(math.atan(value))

    def _sinh(self, value: int | float) -> float:
        # Hyperbolic functions are not angles, so DEG/RAD does not apply.
        return math.sinh(value)

    def _cosh(self, value: int | float) -> float:
        return math.cosh(value)

    def _tanh(self, value: int | float) -> float:
        return math.tanh(value)

    def _sqrt(self, value: int | float) -> float:
        if value < 0:
            raise CalculatorError("Square root is only defined for zero and positive numbers.")
        return math.sqrt(value)

    def _nroot(self, value: int | float, index: int | float) -> int | float:
        """Return the ``index``-th root of ``value``.

        ``nroot(8, 3)`` is 2. Negative values are allowed when the index is
        an odd integer, so ``nroot(-8, 3)`` is -2. Python's own ``**`` would
        produce a complex number for that case, which this calculator avoids.
        """

        if index == 0:
            raise CalculatorError("The root index cannot be zero.")

        whole_index: int | None
        if isinstance(index, int) or index.is_integer():
            whole_index = int(index)
        else:
            whole_index = None

        if value < 0:
            if whole_index is None or whole_index % 2 == 0:
                raise CalculatorError(
                    "Even roots of negative numbers are not real. "
                    "Odd roots are allowed, for example nroot(-8, 3)."
                )
            magnitude = self._safe_pow(abs(value), 1 / whole_index)
            return -magnitude
        return self._safe_pow(value, 1 / index)

    def _absolute(self, value: int | float) -> int | float:
        return abs(value)

    def _percent(self, value: int | float) -> float:
        # 50% is 0.5. Percent applies only to the value on its left:
        # 5+2% is 5.02, while (5+2)% is 0.07.
        return value / 100

    def _factorial(self, value: int | float) -> int:
        if isinstance(value, float):
            if not value.is_integer():
                raise CalculatorError(
                    "Factorial is only defined for whole numbers 0, 1, 2, … up to 1000."
                )
            value = int(value)
        if not isinstance(value, int) or isinstance(value, bool):
            raise CalculatorError(
                "Factorial is only defined for whole numbers 0, 1, 2, … up to 1000."
            )
        if value < 0 or value > MAX_FACTORIAL:
            raise CalculatorError(
                "Factorial is only defined for whole numbers 0, 1, 2, … up to 1000."
            )
        return math.factorial(value)

    def _log(self, value: int | float, base: int | float = 10) -> float:
        """``log(x)`` is base 10. ``log(x, base)`` uses the base you give."""

        if value <= 0:
            raise CalculatorError("Logarithm is only defined for positive numbers.")
        if base <= 0 or base == 1:
            raise CalculatorError("Logarithm base must be positive and not equal to 1.")
        return math.log(value, base)

    def _log10(self, value: int | float) -> float:
        if value <= 0:
            raise CalculatorError("Logarithm is only defined for positive numbers.")
        return math.log10(value)

    def _ln(self, value: int | float) -> float:
        if value <= 0:
            raise CalculatorError("Natural logarithm is only defined for positive numbers.")
        return math.log(value)

    def _exp(self, value: int | float) -> float:
        try:
            return math.exp(value)
        except OverflowError:
            raise CalculatorError("That number is too large to calculate.") from None
