"""The calculator window.

This file draws the buttons and the display. It does not do the maths.
Every time the user presses ``=`` or Enter, the current text is handed to
``calculator.engine.Calculator``. Keeping the two pieces apart means the
number rules can be tested without opening a window.

Run the app with ``python main.py`` or ``python -m calculator``.
Running this file directly does not work, because it is part of the package.
"""

from __future__ import annotations

import re
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
from typing import NamedTuple

from .engine import Calculator, CalculatorError, format_result

# A single number or name, including scientific notation. Used to decide
# whether the x² key can append ^2 or should wrap the whole expression.
_SIMPLE_VALUE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*|(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?"
)

COLOR_BG = "#161922"
COLOR_PANEL = "#1e2430"
COLOR_DISPLAY = "#0e1118"
COLOR_DISPLAY_BORDER = "#2c3444"
COLOR_TEXT = "#f2f4f8"
COLOR_MUTED = "#8b95a8"
COLOR_RESULT = "#f7f8fb"
COLOR_ACCENT = "#6ea8fe"
COLOR_ACCENT_TEXT = "#0d1520"
COLOR_ERROR = "#ff8b98"
COLOR_OK = "#7dcea0"
COLOR_BUTTON = "#2a3142"
COLOR_BUTTON_ACTIVE = "#3a4458"
COLOR_OP = "#303a4f"
COLOR_OP_TEXT = "#9ec1ff"
COLOR_CLEAR = "#e06c75"
COLOR_CLEAR_TEXT = "#1a1014"
COLOR_CONST = "#9ad7c4"

DEFAULT_HINT = "Type an expression or use the buttons. Press Enter or = to calculate."

ABOUT_TEXT = """Engineering Calculator

Type an expression, then press Enter or =.

Examples
  sin(30) + sqrt(49)
  nroot(8, 3)
  log(8, 2)
  6.02E23

% means percent, so 50% is 0.5. It applies to the value on its left.
! means factorial, so 5! is 120.
^ means power, so 2^10 is 1024. Powers group to the right: 2^3^2 is 512.
Ans is the previous result.

DEG / RAD applies to sin, cos, tan and their inverses.
Hyperbolic functions (sinh, cosh, tanh) are not angles.

Memory
  M+   add the current value
  M-   subtract the current value
  MR   insert the stored value
  MC   clear memory

The calculation engine does not use Python's eval function.
Expressions are parsed and only allowed operations are run.
"""


class ButtonSpec(NamedTuple):
    """One key on the calculator.

    ``action`` says what the key does. ``payload`` is the text inserted
    for an ``insert`` action. ``style`` picks the colors.
    """

    label: str
    action: str
    payload: str = ""
    style: str = "fn"
    hint: str = ""
    colspan: int = 1


# The header sits above both key groups. The body is a scientific pad on
# the left and a numeric pad on the right. Equals stretches across the pad.
HEADER_KEYS: list[ButtonSpec] = [
    ButtonSpec("MC", "mem_clear", style="mem", hint="Clear the memory"),
    ButtonSpec("MR", "mem_recall", style="mem", hint="Insert the value stored in memory"),
    ButtonSpec("M+", "mem_add", style="mem", hint="Add the current value to memory"),
    ButtonSpec("M-", "mem_sub", style="mem", hint="Subtract the current value from memory"),
    ButtonSpec("DEG", "angle", style="mode", hint="Toggle degrees and radians"),
    ButtonSpec("Ans", "insert", "Ans", "const", "Insert the previous result"),
    ButtonSpec("⌫", "backspace", style="edit", hint="Delete the character before the cursor"),
    ButtonSpec("C", "clear", style="clear", hint="Clear the current expression (Esc)"),
]

SCIENCE_KEYS: list[list[ButtonSpec]] = [
    [
        ButtonSpec("sin", "insert", "sin(", "fn", "Sine, using the current angle mode"),
        ButtonSpec("cos", "insert", "cos(", "fn", "Cosine, using the current angle mode"),
        ButtonSpec("tan", "insert", "tan(", "fn", "Tangent, using the current angle mode"),
        ButtonSpec("ln", "insert", "ln(", "fn", "Natural logarithm, base e"),
        ButtonSpec("log", "insert", "log10(", "fn", "Base-10 logarithm"),
    ],
    [
        ButtonSpec("sin⁻¹", "insert", "asin(", "fn", "Inverse sine. The result uses DEG or RAD"),
        ButtonSpec("cos⁻¹", "insert", "acos(", "fn", "Inverse cosine"),
        ButtonSpec("tan⁻¹", "insert", "atan(", "fn", "Inverse tangent"),
        ButtonSpec("sinh", "insert", "sinh(", "fn", "Hyperbolic sine (not an angle)"),
        ButtonSpec("cosh", "insert", "cosh(", "fn", "Hyperbolic cosine (not an angle)"),
    ],
    [
        ButtonSpec("tanh", "insert", "tanh(", "fn", "Hyperbolic tangent (not an angle)"),
        ButtonSpec("logₙ", "insert", "log(", "fn", "log(x, base) — logarithm in the base you choose"),
        ButtonSpec("√", "insert", "sqrt(", "fn", "Square root"),
        ButtonSpec("ⁿ√", "insert", "nroot(", "fn", "nroot(x, n) — the nth root of x"),
        ButtonSpec("x²", "square", style="fn", hint="Square the whole expression"),
    ],
    [
        ButtonSpec("1/x", "reciprocal", style="fn", hint="Wrap the expression as 1/(...)"),
        ButtonSpec("n!", "insert", "!", "fn", "Factorial of the value just before !"),
        ButtonSpec("%", "insert", "%", "fn", "Percent. 50% means 0.5"),
        ButtonSpec("abs", "insert", "abs(", "fn", "Absolute value"),
        ButtonSpec("EXP", "insert", "E", "fn", "Scientific notation, for example 6.02E23"),
    ],
    [
        ButtonSpec("π", "insert", "pi", "const", "The constant pi"),
        ButtonSpec("e", "insert", "e", "const", "Euler's number"),
        ButtonSpec("(", "insert", "(", "op", "Open a parenthesis"),
        ButtonSpec(")", "insert", ")", "op", "Close a parenthesis"),
        ButtonSpec(",", "insert", ",", "op", "Separate arguments, as in log(8, 2)"),
    ],
]

NUMBER_KEYS: list[list[ButtonSpec]] = [
    [
        ButtonSpec("7", "insert", "7", "num"),
        ButtonSpec("8", "insert", "8", "num"),
        ButtonSpec("9", "insert", "9", "num"),
        ButtonSpec("÷", "insert", "/", "op", "Divide"),
    ],
    [
        ButtonSpec("4", "insert", "4", "num"),
        ButtonSpec("5", "insert", "5", "num"),
        ButtonSpec("6", "insert", "6", "num"),
        ButtonSpec("×", "insert", "*", "op", "Multiply"),
    ],
    [
        ButtonSpec("1", "insert", "1", "num"),
        ButtonSpec("2", "insert", "2", "num"),
        ButtonSpec("3", "insert", "3", "num"),
        ButtonSpec("−", "insert", "-", "op", "Subtract, or start a negative number"),
    ],
    [
        ButtonSpec("0", "insert", "0", "num"),
        ButtonSpec(".", "insert", ".", "num", "Decimal point"),
        ButtonSpec("^", "insert", "^", "op", "Power. 2^3 is 8. 2^3^2 is 512"),
        ButtonSpec("+", "insert", "+", "op", "Add"),
    ],
    [
        ButtonSpec("=", "equals", style="eq", hint="Evaluate the expression (Enter or =)", colspan=4),
    ],
]

STYLES = {
    "num": {"bg": COLOR_BUTTON, "fg": COLOR_TEXT, "active": COLOR_BUTTON_ACTIVE},
    "fn": {"bg": COLOR_BUTTON, "fg": COLOR_TEXT, "active": COLOR_BUTTON_ACTIVE},
    "op": {"bg": COLOR_OP, "fg": COLOR_OP_TEXT, "active": "#3d4c68"},
    "eq": {"bg": COLOR_ACCENT, "fg": COLOR_ACCENT_TEXT, "active": "#8ebbff"},
    "clear": {"bg": COLOR_CLEAR, "fg": COLOR_CLEAR_TEXT, "active": "#ef8d95"},
    "mem": {"bg": COLOR_OP, "fg": COLOR_TEXT, "active": "#3d4c68"},
    "edit": {"bg": COLOR_OP, "fg": COLOR_TEXT, "active": "#3d4c68"},
    "mode": {"bg": "#243628", "fg": COLOR_OK, "active": "#305438"},
    # Same key color as the other functions; the green text marks constants.
    "const": {"bg": COLOR_BUTTON, "fg": COLOR_CONST, "active": COLOR_BUTTON_ACTIVE},
}


def square_text(expression: str) -> str:
    """Return an expression that squares ``expression``.

    A single number or name gets ``^2`` on the end: ``5`` becomes ``5^2``.
    A longer expression is wrapped so the whole thing is squared:
    ``2+3`` becomes ``(2+3)^2``. An empty box squares Ans.
    """

    text = expression.strip()
    if not text:
        return "Ans^2"
    if _SIMPLE_VALUE.fullmatch(text):
        return f"{text}^2"
    return f"({text})^2"


def reciprocal_text(expression: str) -> str:
    """Return ``1`` divided by ``expression``.

    An empty box becomes ``1/(`` so typing can continue. Anything else is
    wrapped: ``2+3`` becomes ``1/(2+3)``.
    """

    text = expression.strip()
    if not text:
        return "1/("
    return f"1/({text})"


def _first_font(families: set[str], candidates: tuple[str, ...]) -> str:
    for name in candidates:
        if name in families:
            return name
    return tkfont.nametofont("TkDefaultFont").cget("family")


class CalculatorApp:
    """Build the window and connect each key to the engine."""

    def __init__(self, root: tk.Tk, engine: Calculator | None = None) -> None:
        self.root = root
        self.engine = engine if engine is not None else Calculator()
        # The expression that produced the number currently on screen.
        # Memory keys reuse that number instead of calculating it twice.
        self._synced_expression: str | None = None
        self._displayed_value: int | float = 0
        self._refreshing_history = False
        self.buttons: dict[str, tk.Button] = {}
        self.angle_button: tk.Button | None = None

        self._load_fonts()
        self._configure_window()
        self._build_menu()
        self._build_layout()
        self._bind_keys()
        self._set_result("0", error=False)
        self._refresh_status()
        self._set_hint(DEFAULT_HINT)
        self.entry.focus_set()

    def _load_fonts(self) -> None:
        families = set(tkfont.families())
        ui = _first_font(families, ("DejaVu Sans", "Ubuntu", "Liberation Sans", "Nimbus Sans"))
        mono = _first_font(families, ("DejaVu Sans Mono", "Ubuntu Mono", "Liberation Mono"))
        self.font_ui = (ui, 11)
        self.font_small = (ui, 10)
        self.font_button = (ui, 12)
        self.font_title = (ui, 13, "bold")
        self.font_expr = (mono, 13)
        self.font_result = (mono, 22)
        self.font_history = (mono, 11)

    def _configure_window(self) -> None:
        self.root.title("Engineering Calculator")
        self.root.configure(bg=COLOR_BG)
        self.root.geometry("1180x740+60+30")
        self.root.minsize(1040, 660)

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        self.root.configure(menu=menu)

        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="Quit", command=self.root.destroy)
        menu.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=0)
        edit_menu.add_command(label="Clear", command=self.clear_expression, accelerator="Esc")
        edit_menu.add_command(label="Backspace", command=self.backspace, accelerator="Backspace")
        menu.add_cascade(label="Edit", menu=edit_menu)

        mode_menu = tk.Menu(menu, tearoff=0)
        mode_menu.add_command(label="Degrees", command=lambda: self.set_angle("DEG"))
        mode_menu.add_command(label="Radians", command=lambda: self.set_angle("RAD"))
        menu.add_cascade(label="Mode", menu=mode_menu)

        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menu.add_cascade(label="Help", menu=help_menu)

    def _build_layout(self) -> None:
        outer = tk.Frame(self.root, bg=COLOR_BG)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=0, minsize=360)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        self._build_history(outer)
        self._build_workspace(outer)

    def _build_history(self, parent: tk.Widget) -> None:
        panel = tk.Frame(parent, bg=COLOR_PANEL)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)

        tk.Label(
            panel,
            text="History",
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            font=self.font_title,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))

        list_frame = tk.Frame(panel, bg=COLOR_PANEL)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=12)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        y_scroll = tk.Scrollbar(list_frame, orient="vertical")
        x_scroll = tk.Scrollbar(list_frame, orient="horizontal")
        self.history_list = tk.Listbox(
            list_frame,
            bg=COLOR_DISPLAY,
            fg=COLOR_TEXT,
            font=self.font_history,
            selectbackground=COLOR_ACCENT,
            selectforeground=COLOR_ACCENT_TEXT,
            highlightthickness=0,
            relief="flat",
            activestyle="none",
            exportselection=False,
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )
        y_scroll.configure(command=self.history_list.yview)
        x_scroll.configure(command=self.history_list.xview)
        self.history_list.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.history_list.bind("<<ListboxSelect>>", self.on_history_select)

        clear_history = tk.Button(
            panel,
            text="Clear history",
            command=self.clear_history,
            font=self.font_small,
            bg=COLOR_BUTTON,
            fg=COLOR_TEXT,
            activebackground=COLOR_BUTTON_ACTIVE,
            activeforeground=COLOR_TEXT,
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=False,
            padx=8,
            pady=6,
        )
        clear_history.grid(row=2, column=0, sticky="ew", padx=12, pady=12)
        clear_history.bind("<Enter>", lambda _event: self._set_hint("Remove past calculations. Ans and memory stay."))
        clear_history.bind("<Leave>", lambda _event: self._set_hint(DEFAULT_HINT))

    def _build_workspace(self, parent: tk.Widget) -> None:
        workspace = tk.Frame(parent, bg=COLOR_BG)
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.rowconfigure(3, weight=1)
        workspace.columnconfigure(0, weight=1)

        tk.Label(
            workspace,
            text="Engineering Calculator",
            bg=COLOR_BG,
            fg=COLOR_TEXT,
            font=self.font_title,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))

        self._build_display(workspace)
        self._build_header(workspace)
        self._build_body(workspace)
        self._build_status(workspace)

    def _build_display(self, parent: tk.Widget) -> None:
        self.display = tk.Frame(
            parent,
            bg=COLOR_DISPLAY,
            highlightbackground=COLOR_DISPLAY_BORDER,
            highlightthickness=1,
        )
        self.display.grid(row=1, column=0, sticky="ew", padx=16, pady=(10, 8))

        top = tk.Frame(self.display, bg=COLOR_DISPLAY)
        top.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(
            top,
            text="Expression",
            bg=COLOR_DISPLAY,
            fg=COLOR_MUTED,
            font=self.font_small,
        ).pack(side="left")
        self.memory_badge = tk.Label(
            top,
            text="",
            width=2,
            bg=COLOR_DISPLAY,
            fg=COLOR_OK,
            font=self.font_small,
        )
        self.memory_badge.pack(side="right")
        self.angle_badge = tk.Label(
            top,
            text="DEG",
            width=4,
            bg=COLOR_DISPLAY,
            fg=COLOR_ACCENT,
            font=self.font_small,
        )
        self.angle_badge.pack(side="right")

        self.expression = tk.StringVar()
        self.entry = tk.Entry(
            self.display,
            textvariable=self.expression,
            font=self.font_expr,
            bg=COLOR_DISPLAY,
            fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT,
            relief="flat",
            justify="right",
            borderwidth=0,
            highlightthickness=0,
        )
        self.entry.pack(fill="x", padx=14, pady=(4, 0))

        self.result_entry = tk.Entry(
            self.display,
            font=self.font_result,
            bg=COLOR_DISPLAY,
            fg=COLOR_RESULT,
            readonlybackground=COLOR_DISPLAY,
            relief="flat",
            justify="right",
            borderwidth=0,
            highlightthickness=0,
        )
        self.result_entry.pack(fill="x", padx=14, pady=(2, 12))

        self.entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.entry.bind("<FocusOut>", self._on_entry_focus_out)
        # Editing the text means the on-screen number may no longer match it.
        self.expression.trace_add("write", self._on_expression_edit)

    def _build_header(self, parent: tk.Widget) -> None:
        header = tk.Frame(parent, bg=COLOR_BG)
        header.grid(row=2, column=0, sticky="ew", padx=13, pady=(0, 2))
        for column in range(len(HEADER_KEYS)):
            header.columnconfigure(column, weight=1, uniform="header")
        for column, spec in enumerate(HEADER_KEYS):
            button = self._make_button(header, spec)
            button.grid(row=0, column=column, sticky="nsew", padx=3, pady=3)

    def _build_body(self, parent: tk.Widget) -> None:
        body = tk.Frame(parent, bg=COLOR_BG)
        body.grid(row=3, column=0, sticky="nsew", padx=13, pady=(0, 4))
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=1)

        science = tk.Frame(body, bg=COLOR_BG)
        science.grid(row=0, column=0, sticky="nsew")
        numbers = tk.Frame(body, bg=COLOR_BG)
        numbers.grid(row=0, column=1, sticky="nsew")
        self._place_grid(science, SCIENCE_KEYS)
        self._place_grid(numbers, NUMBER_KEYS)

    def _build_status(self, parent: tk.Widget) -> None:
        status_frame = tk.Frame(parent, bg=COLOR_BG)
        status_frame.grid(row=4, column=0, sticky="ew", padx=16, pady=(2, 12))
        self.status_label = tk.Label(
            status_frame,
            text="",
            bg=COLOR_BG,
            fg=COLOR_MUTED,
            font=self.font_small,
            anchor="w",
        )
        self.status_label.pack(fill="x")
        self.hint_label = tk.Label(
            status_frame,
            text="",
            bg=COLOR_BG,
            fg=COLOR_MUTED,
            font=self.font_small,
            anchor="w",
        )
        self.hint_label.pack(fill="x")

    def _place_grid(self, parent: tk.Widget, rows: list[list[ButtonSpec]]) -> None:
        column_count = max(sum(spec.colspan for spec in row) for row in rows)
        for column in range(column_count):
            parent.columnconfigure(column, weight=1, uniform=f"cols-{id(parent)}")
        for row_index, row in enumerate(rows):
            parent.rowconfigure(row_index, weight=1)
            column = 0
            for spec in row:
                button = self._make_button(parent, spec)
                button.grid(
                    row=row_index,
                    column=column,
                    columnspan=spec.colspan,
                    sticky="nsew",
                    padx=3,
                    pady=3,
                )
                column += spec.colspan

    def _make_button(self, parent: tk.Widget, spec: ButtonSpec) -> tk.Button:
        style = STYLES[spec.style]
        button = tk.Button(
            parent,
            text=spec.label,
            command=lambda chosen=spec: self._activate(chosen),
            font=self.font_button if spec.style != "eq" else (self.font_button[0], 14, "bold"),
            bg=style["bg"],
            fg=style["fg"],
            activebackground=style["active"],
            activeforeground=style["fg"] if spec.style != "eq" else COLOR_ACCENT_TEXT,
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=False,
            padx=4,
            pady=8,
        )
        self.buttons[spec.label] = button
        if spec.action == "angle":
            self.angle_button = button
        if spec.hint:
            button.bind("<Enter>", lambda _event, hint=spec.hint: self._set_hint(hint))
            button.bind("<Leave>", lambda _event: self._set_hint(DEFAULT_HINT))
        return button

    def _bind_keys(self) -> None:
        # Bind on the entry, and return "break", so "=" calculates instead
        # of being typed into the expression.
        self.entry.bind("<Return>", self._on_evaluate_key)
        self.entry.bind("<KP_Enter>", self._on_evaluate_key)
        self.entry.bind("=", self._on_evaluate_key)
        self.entry.bind("<Escape>", self._on_escape)
        self.root.bind("<Escape>", self._on_escape)
        for keysym, text in (
            ("<KP_Add>", "+"),
            ("<KP_Subtract>", "-"),
            ("<KP_Multiply>", "*"),
            ("<KP_Divide>", "/"),
            ("<KP_Decimal>", "."),
        ):
            self.entry.bind(keysym, lambda _event, value=text: self._on_insert_key(value))

    def _activate(self, spec: ButtonSpec) -> None:
        action = spec.action
        if action == "insert":
            self.insert_text(spec.payload)
        elif action == "equals":
            self.evaluate_current()
        elif action == "clear":
            self.clear_expression()
        elif action == "backspace":
            self.backspace()
        elif action == "angle":
            self.toggle_angle()
        elif action == "mem_clear":
            self.memory_clear()
        elif action == "mem_recall":
            self.memory_recall()
        elif action == "mem_add":
            self.memory_add()
        elif action == "mem_sub":
            self.memory_subtract()
        elif action == "square":
            self.apply_square()
        elif action == "reciprocal":
            self.apply_reciprocal()
        self.entry.focus_set()

    def insert_text(self, text: str) -> None:
        """Insert ``text`` at the cursor, replacing a selection if there is one."""

        if self.entry.selection_present():
            self.entry.delete("sel.first", "sel.last")
        self.entry.insert("insert", text)
        self.entry.focus_set()

    def clear_expression(self) -> None:
        """Clear the expression and show 0. Ans, memory, and history stay."""

        self.expression.set("")
        self._synced_expression = None
        self._displayed_value = 0
        self._set_result("0", error=False)
        self.entry.focus_set()

    def backspace(self) -> None:
        if self.entry.selection_present():
            self.entry.delete("sel.first", "sel.last")
        else:
            cursor = self.entry.index("insert")
            if cursor:
                self.entry.delete(cursor - 1)
        self.entry.focus_set()

    def apply_square(self) -> None:
        self.expression.set(square_text(self.expression.get()))
        self.entry.icursor("end")
        self.entry.focus_set()

    def apply_reciprocal(self) -> None:
        self.expression.set(reciprocal_text(self.expression.get()))
        # The cursor sits after the inserted text, ready for Enter or more typing.
        self.entry.icursor("end")
        self.entry.focus_set()

    def evaluate_current(self) -> None:
        """Send the expression to the engine and show the result or an error."""

        try:
            value = self.engine.evaluate(self.expression.get())
        except CalculatorError as error:
            self._set_result(str(error), error=True)
            return

        self._synced_expression = self.expression.get().strip()
        self._displayed_value = value
        self._set_result(format_result(value), error=False)
        self._refresh_history()
        self._refresh_status()

    def set_angle(self, mode: str) -> None:
        self.engine.set_angle_mode(mode)
        self._update_angle_widgets()
        self._refresh_status()

    def toggle_angle(self) -> None:
        self.engine.toggle_angle_mode()
        self._update_angle_widgets()
        self._refresh_status()

    def memory_add(self) -> None:
        self._update_memory(self.engine.memory_add)

    def memory_subtract(self) -> None:
        self._update_memory(self.engine.memory_subtract)

    def memory_clear(self) -> None:
        self.engine.memory_clear()
        self._refresh_status()
        self.entry.focus_set()

    def memory_recall(self) -> None:
        text = format_result(self.engine.memory_recall())
        # Parentheses keep a negative memory from sticking to the previous operator.
        if text.startswith("-"):
            text = f"({text})"
        self.insert_text(text)

    def clear_history(self) -> None:
        self.engine.clear_history()
        self._refresh_history()
        self.entry.focus_set()

    def show_about(self) -> None:
        messagebox.showinfo("About Engineering Calculator", ABOUT_TEXT, parent=self.root)

    def result_text(self) -> str:
        return self.result_entry.get()

    def on_history_select(self, _event: object = None) -> None:
        """Load the selected calculation back into the expression box."""

        if self._refreshing_history:
            return
        selection = self.history_list.curselection()
        if not selection:
            return
        item = self.engine.history[selection[0]]
        self.expression.set(item.expression)
        self._set_result(item.result, error=False)
        self.entry.icursor("end")
        self.entry.focus_set()

    def _update_memory(self, operation) -> None:
        try:
            value = self._value_for_memory()
        except CalculatorError as error:
            self._set_result(str(error), error=True)
            return
        operation(value)
        self._refresh_status()
        self.entry.focus_set()

    def _value_for_memory(self) -> int | float:
        """The number M+ and M- should use.

        A non-empty expression is calculated first, unless it is already the
        expression on screen. An empty box uses the number currently shown
        (0 after Clear).
        """

        expression = self.expression.get().strip()
        if not expression:
            return self._displayed_value
        if expression == self._synced_expression:
            return self._displayed_value
        value = self.engine.evaluate(expression)
        self._synced_expression = expression
        self._displayed_value = value
        self._set_result(format_result(value), error=False)
        self._refresh_history()
        return value

    def _on_expression_edit(self, *_args: object) -> None:
        if self.expression.get().strip() != self._synced_expression:
            self._synced_expression = None

    def _on_entry_focus_in(self, _event: object) -> None:
        self.display.configure(highlightbackground=COLOR_ACCENT)

    def _on_entry_focus_out(self, _event: object) -> None:
        self.display.configure(highlightbackground=COLOR_DISPLAY_BORDER)

    def _on_evaluate_key(self, _event: object = None) -> str:
        self.evaluate_current()
        return "break"

    def _on_escape(self, _event: object = None) -> str:
        self.clear_expression()
        return "break"

    def _on_insert_key(self, text: str) -> str:
        self.insert_text(text)
        return "break"

    def _set_result(self, text: str, *, error: bool) -> None:
        self.result_entry.configure(state="normal")
        self.result_entry.delete(0, "end")
        self.result_entry.insert(0, text)
        self.result_entry.configure(
            state="readonly",
            fg=COLOR_ERROR if error else COLOR_RESULT,
            readonlybackground=COLOR_DISPLAY,
            justify="left" if error else "right",
        )

    def _set_hint(self, text: str) -> None:
        self.hint_label.configure(text=text)

    def _update_angle_widgets(self) -> None:
        mode = self.engine.angle_mode
        self.angle_badge.configure(text=mode)
        if self.angle_button is not None:
            self.angle_button.configure(text=mode)

    def _refresh_status(self) -> None:
        mode_name = "degrees" if self.engine.angle_mode == "DEG" else "radians"
        memory_text = format_result(self.engine.memory)
        self.status_label.configure(text=f"Angles: {mode_name}    Memory: {memory_text}")
        self.angle_badge.configure(text=self.engine.angle_mode)
        self.memory_badge.configure(text="M" if self.engine.memory != 0 else "")

    def _refresh_history(self) -> None:
        self._refreshing_history = True
        try:
            self.history_list.delete(0, "end")
            for item in self.engine.history:
                self.history_list.insert("end", f"{item.expression} = {item.result}")
            if self.engine.history:
                self.history_list.see("end")
        finally:
            self._refreshing_history = False


def main() -> None:
    """Open the window and run until it is closed."""

    try:
        root = tk.Tk()
    except tk.TclError as error:
        sys.stderr.write(
            "Could not open a window. A graphical display is required.\n"
            f"({error})\n"
        )
        sys.exit(1)
    CalculatorApp(root)
    root.mainloop()
