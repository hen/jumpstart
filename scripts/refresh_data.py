#!/usr/bin/env python3

import argparse
from pathlib import Path

from fetch_jumpstart_fronts import write_payload_files


def discover_set_codes(project_root: Path) -> list[str]:
    data_dir = project_root / "docs" / "data"
    set_codes = {path.stem.lower() for path in data_dir.glob("*.json")}
    set_codes.update(path.name[: -len("-owned.txt")].lower() for path in project_root.glob("*-owned.txt"))
    return sorted(set_codes)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate Jumpstart data files after owned-pack lists or source data changes."
    )
    parser.add_argument(
        "set_codes",
        nargs="*",
        help="Optional set codes to refresh. Defaults to all known sets from docs/data and *-owned.txt files.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    set_codes = [set_code.lower() for set_code in args.set_codes] or discover_set_codes(project_root)

    if not set_codes:
        raise SystemExit("No set codes found to refresh.")

    for set_code in set_codes:
        write_payload_files(project_root, set_code)


if __name__ == "__main__":
    main()
