#!/usr/bin/env python3
"""List commits whose subject starts with ticket keys, as CSV.

All arguments are passed through to `git log`.
The subject may start with a comma-separated list of keys, e.g.
"PS-11220, PS-11065 [8.4]: OIDC ..."; one row is written per key.
Output columns: ticket, short hash, subject without the leading key list
(sorted by ticket, stable).
"""
import csv
import re
import subprocess
import sys

TICKET = r"(?:PS|DISTMYSQL|PXC|PXB)-[0-9]+"
TICKET_RE = re.compile(TICKET)
# Leading list of keys separated by commas, plus the whitespace after it.
TICKET_LIST_RE = re.compile(rf"^({TICKET}(?:\s*,\s*{TICKET})*)\s*")


def main(argv: list[str]) -> int:
    if not argv:
        prog = sys.argv[0]
        print(f"Usage: {prog} <git-log-arguments...>", file=sys.stderr)
        print(f"Example: {prog} release-8.0.40-31..release-8.0.41-32", file=sys.stderr)
        return 2

    try:
        proc = subprocess.run(
            ["git", "log", "--no-color", "--format=%h%x1f%s%x1e", *argv],
            stdout=subprocess.PIPE,
        )
    except FileNotFoundError:
        print("Error: git not found in PATH", file=sys.stderr)
        return 127
    if proc.returncode != 0:
        return proc.returncode

    rows = []
    for record in proc.stdout.split(b"\x1e"):
        record = record.strip(b"\r\n")
        if not record:
            continue
        try:
            commit_hash, subject = record.split(b"\x1f", 1)
        except ValueError:
            print(f"Error: malformed git log record: {record!r}", file=sys.stderr)
            return 1

        hash_text = commit_hash.decode("utf-8", "surrogateescape")
        subject_text = subject.decode("utf-8", "surrogateescape")

        match = TICKET_LIST_RE.match(subject_text)
        if not match:
            continue
        rest = subject_text[match.end():]
        # dict.fromkeys drops repeated keys but keeps their order.
        for ticket in dict.fromkeys(TICKET_RE.findall(match.group(1))):
            rows.append((ticket, hash_text, rest))

    # Keep non-UTF-8 bytes intact on output instead of crashing.
    sys.stdout.reconfigure(errors="surrogateescape")
    writer = csv.writer(sys.stdout, lineterminator="\n", quoting=csv.QUOTE_ALL)
    writer.writerows(sorted(rows, key=lambda row: row[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
