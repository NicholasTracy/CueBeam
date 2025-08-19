#!/usr/bin/env python3
from pathlib import Path
import sys

p = Path("VERSION")
v = p.read_text(encoding="utf-8").strip()
parts = v.lstrip("v").split(".")
if len(parts) != 3:
    print("VERSION must be semver, e.g. 0.1.0")
    sys.exit(1)
major, minor, patch = map(int, parts)
arg = sys.argv[1] if len(sys.argv) > 1 else "patch"
if arg == "major":
    major += 1; minor = 0; patch = 0
elif arg == "minor":
    minor += 1; patch = 0
else:
    patch += 1
nv = f"{major}.{minor}.{patch}"
p.write_text(nv + "\n", encoding="utf-8")
print(nv)
