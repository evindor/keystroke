"""Bounded arithmetic parser. Never eval user input."""
import ast
import math
import operator
import re
from flint.api import row, copy, navigate, score

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
       ast.FloorDiv: operator.floordiv}
FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
         "log": math.log10, "ln": math.log, "abs": abs, "round": round,
         "ceil": math.ceil, "floor": math.floor}


def calculate(text):
    if len(text) > 256:
        raise ValueError("Expression too long")
    text = text.strip().lstrip("=").strip().replace("×", "*").replace("÷", "/").replace("^", "**")
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%\s+of\s+", r"(\1/100)*", text, flags=re.I)
    text = re.sub(r"(\d+(?:\.\d+)?)%(?!\s*\d)", r"(\1/100)", text)
    tree = ast.parse(text, mode="eval")
    if len(list(ast.walk(tree))) > 90:
        raise ValueError("Expression too complex")
    def visit(n):
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            value = float(n.value)
        elif isinstance(n, ast.Name) and n.id in {"pi", "e", "tau"}:
            value = getattr(math, n.id)
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            value = visit(n.operand) * (-1 if isinstance(n.op, ast.USub) else 1)
        elif isinstance(n, ast.BinOp) and type(n.op) in OPS:
            a, b = visit(n.left), visit(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 1000 or abs(a) > 1e100):
                raise ValueError("Exponent too large")
            value = OPS[type(n.op)](a, b)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS and len(n.args) == 1 and not n.keywords:
            value = FUNCS[n.func.id](visit(n.args[0]))
        else:
            raise ValueError("Unsupported expression")
        if isinstance(value, complex) or not math.isfinite(value) or abs(value) > 1e150:
            raise ValueError("Result out of range")
        return value
    return visit(tree.body)


async def query(ctx):
    if ctx.scope and ctx.scope != "flint.calculator":
        return []
    if not ctx.query:
        return [row("calc", "Calculator", "Try 128 * 1.24 or 15% of 80", "󰃬", action=navigate("flint.calculator"), order=3, score=24)] if not ctx.scope else []
    s = score(ctx.query, "Calculator", "arithmetic math")
    if s and not ctx.scope:
        return [row("calc", "Calculator", "Try 128 * 1.24 or 15% of 80", "󰃬", action=navigate("flint.calculator"), score=s)]
    try:
        value = calculate(ctx.query)
    except SyntaxError:
        partial = ctx.query.strip()
        prefix = re.sub(r"[+\-*/^×÷]+\s*$", "", partial).strip()
        try:
            if prefix == partial:
                return []
            calculate(prefix)
        except (ValueError, SyntaxError, TypeError, ZeroDivisionError, OverflowError):
            return []
        return [row("result", partial + " …", "Continue your calculation", "󰃬", score=200,
                    action={"type": "noop"}, disabled=True, verb="Keep typing",
                    preview=partial + " …", previewLabel="CALCULATOR", previewDetail="Add the next number")]
    except (ValueError, TypeError, ZeroDivisionError, OverflowError):
        return []
    result = f"{value:.{ctx.settings['precision']}g}"
    return [row("result", result, ctx.query + " =", "󰃬", score=200, action=copy(result), verb="Copy result",
                preview=result, previewLabel="RESULT", previewDetail=ctx.query)]
