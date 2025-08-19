#!/usr/bin/env python3
import pathlib
import sys

VERSION_FILE = pathlib.Path(__file__).parent.parent / "VERSION"


def bump(part: str) -> str:
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    major, minor, patch = map(int, version.split("."))
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"unknown part {part!r}")
    new_version = f"{major}.{minor}.{patch}"
    VERSION_FILE.write_text(new_version, encoding="utf-8")
    return new_version


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: bump_version.py [major|minor|patch]")
        sys.exit(1)
    part = sys.argv[1]
    try:
        new_ver = bump(part)
    except ValueError as e:
        print(e)
        sys.exit(1)
    print(f"Bumped version to {new_ver}")