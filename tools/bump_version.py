#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def read_version(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def write_version(path: Path, v: str) -> None:
    path.write_text(v.strip(), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Bump version.txt and echo new version")
    ap.add_argument("version", help="New version like 1.2.3")
    ap.add_argument("--file", default="version.txt", help="Path to version file")
    args = ap.parse_args()

    path = Path(args.file)
    write_version(path, args.version)
    print(args.version)


if __name__ == "__main__":
    main()
