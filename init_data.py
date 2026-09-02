from __future__ import annotations

import argparse
from pathlib import Path

from data_pipeline.sqlite_loader import DB_PATH, load_from_xls


ROOT = Path(__file__).resolve().parent
DEFAULT_XLS = ROOT / "20260713.xls"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import shipping XLS rates into SQLite")
    parser.add_argument("xls_path", nargs="?", type=Path, default=DEFAULT_XLS)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()

    count = load_from_xls(args.xls_path, args.db)
    print(f"Imported {count} rate rows into {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
