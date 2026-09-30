#!/usr/bin/env python3
"""Join two CSV files on their first column and write the result as CSV.

Usage: csv-join.py <file1> <file2> <join-type>

Join types (short form in brackets):
  outleft  (l)  rows from file1 whose first-column key does not appear in file2
  outright (r)  rows from file2 whose first-column key does not appear in file1

Rows are written unchanged, in their original order. Files have no header
row (matching the output of git-log-csv.py and fix-ver-tickets.py).
"""
import csv
import sys


def read_rows(path: str) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return [row for row in csv.reader(f) if row]


def keys(rows: list[list[str]]) -> set[str]:
    return {row[0] for row in rows}


def outleft(left, right):
    right_keys = keys(right)
    return [row for row in left if row[0] not in right_keys]


def outright(left, right):
    left_keys = keys(left)
    return [row for row in right if row[0] not in left_keys]


JOINS = {
    "outleft": outleft,
    "outright": outright,
}

# Short forms of the join types.
ALIASES = {
    "l": "outleft",
    "r": "outright",
}


def usage(prog: str) -> None:
    print(f"Usage: {prog} <file1> <file2> <join-type>", file=sys.stderr)
    short = {name: alias for alias, name in ALIASES.items()}
    types = ", ".join(f"{name} ({short[name]})" if name in short else name for name in JOINS)
    print(f"Join types: {types}", file=sys.stderr)
    print(f"Example: {prog} commits.csv tickets.csv outleft", file=sys.stderr)


def main(argv: list[str]) -> int:
    prog = sys.argv[0]
    if len(argv) != 3:
        usage(prog)
        return 2

    file1, file2, join_type = argv
    join = JOINS.get(ALIASES.get(join_type, join_type))
    if join is None:
        print(f"Error: unknown join type: {join_type}", file=sys.stderr)
        usage(prog)
        return 2

    try:
        left = read_rows(file1)
        right = read_rows(file2)
    except OSError as e:
        print(f"Error: cannot read {e.filename}: {e.strerror}", file=sys.stderr)
        return 1

    writer = csv.writer(sys.stdout, lineterminator="\n", quoting=csv.QUOTE_ALL)
    writer.writerows(join(left, right))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
