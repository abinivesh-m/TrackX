"""Temporary diagnostic script to find invalid escape sequences and syntax errors."""
import ast
import pathlib
import re
import sys
import warnings

root = pathlib.Path(".")

issues = []
checked = 0

def is_skippable(s: str) -> bool:
    parts = s.replace("\\", "/").split("/")
    skip_dirs = {
        "node_modules", "__pycache__", ".pytest_cache", ".venv", "venv",
        "site-packages", ".git", "runs", "temp_frames", "Screenshots",
        "outputs", ".streamlit",
    }
    return any(p in skip_dirs for p in parts)

for p in root.rglob("*.py"):
    rel = str(p.relative_to(root))
    if is_skippable(rel):
        continue
    checked += 1
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = p.read_text(encoding="latin-1")
    # 1. Parse check
    try:
        ast.parse(text, filename=rel)
    except SyntaxError as e:
        issues.append((rel, "SyntaxError", e.lineno, e.msg))
        continue
    # 2. Invalid escape sequences: re-run parse with SyntaxWarning promoted to error
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            ast.parse(text, filename=rel)
    except SyntaxWarning as e:
        issues.append((rel, "InvalidEscape", 0, str(e)))
    except SyntaxError as e:
        issues.append((rel, "SyntaxError", e.lineno, e.msg))

print(f"Checked {checked} files")
for issue in issues:
    print(issue)
print("TOTAL_ISSUES", len(issues))