#!/usr/bin/env python3
"""Validate application version/changelog metadata without importing the legacy app."""
import argparse
from pathlib import Path
import re
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Release tag; must exactly match version.txt")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = (root / "version.txt").read_text().strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        sys.exit("version.txt must contain a three-component numeric version")
    changelog = (root / "changelog.md").read_text()
    if "----------" not in changelog:
        sys.exit("Missing legacy changelog separator")
    first = re.search(r"^###\s+([^\r\n]+)", changelog.split("----------", 1)[1], re.MULTILINE)
    if first is None or first.group(1).strip() != version:
        sys.exit("First changelog version must match version.txt")
    if args.tag is not None and args.tag != version:
        sys.exit("Release tag must exactly match version.txt")
    print("Release metadata consistent: " + version)


if __name__ == "__main__":
    main()
