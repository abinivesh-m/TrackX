import sys

text = open("dashboard/dashboard.py", encoding="utf-8", errors="replace").read()
lines = text.splitlines()
for i, line in enumerate(lines, 1):
    if "\ufffd" in line:
        print(i, repr(line))