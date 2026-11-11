"""Checks the project rules in CONTRIBUTING.md.

    python tools/check_api.py

Stops at the first problem: prints it and exits with status 1. Prints "check_api: OK" when there is none.
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_LINES = 30


def problems(root: Path = ROOT) -> list[str]:
    """Every violation of the rules, in the order of CONTRIBUTING.md."""
    found: list[str] = []
    tree = ast.parse((root / "tables.py").read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    public = [function for function in functions if not function.name.startswith("_")]
    for function in public:
        if ast.get_docstring(function) is None:
            found.append(f"rule 1: {function.name} has no docstring")
        arguments = function.args
        every = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
        every += [extra for extra in (arguments.vararg, arguments.kwarg) if extra is not None]
        missing = [argument.arg for argument in every if argument.annotation is None]
        if missing:
            found.append(f"rule 1: {function.name} has parameters without type annotations: {', '.join(missing)}")
        if function.returns is None:
            found.append(f"rule 1: {function.name} has no return annotation")
    for function in ast.walk(tree):
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = (function.end_lineno or function.lineno) - function.lineno + 1
            if length > MAX_LINES:
                found.append(f"rule 2: {function.name} is {length} lines long, the limit is {MAX_LINES}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
            found.append(f"rule 3: print() is called on line {node.lineno} of tables.py")
    names = sorted(function.name for function in public)
    exported = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            try:
                exported = list(ast.literal_eval(node.value))
            except ValueError:
                exported = None
    if exported != names:
        found.append(f"rule 4: __all__ in tables.py should be {names}, found {exported}")
    headings = re.findall(r"^### +`?(\w+)`?[ \t]*$", (root / "docs" / "API.md").read_text(encoding="utf-8"), re.M)
    if headings != names:
        found.append(f"rule 5: the '### name' headings in docs/API.md should be {names}, found {headings}")
    sections = re.split(r"^### .*$", (root / "docs" / "API.md").read_text(encoding="utf-8"), flags=re.M)[1:]
    if any(not section.strip() for section in sections):
        found.append("rule 5: a heading in docs/API.md has no description under it")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    for name in names:
        if f"`{name}`" not in changelog:
            found.append(f"rule 6: CHANGELOG.md does not mention `{name}`")
    return found


def main() -> int:
    found = problems()
    if found:
        print(f"check_api: FAILED\n{found[0]}")
        return 1
    print("check_api: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
