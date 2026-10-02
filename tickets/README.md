# tickets

Scripts for comparing the JIRA tickets assigned to a fix version with the
commits that went into a release. All scripts write CSV without a header
row, with every field quoted, so their output can be fed to each other.

Requirements: Python 3 standard library only (`jira-ticket.py` runs on 3.8+,
`git-log-tickets.py` and `csv-join.py` need 3.9+), plus `git` for
`git-log-tickets.py`.

## git-log-tickets.py

Lists commits whose subject starts with ticket keys (`PS-`, `DISTMYSQL-`,
`PXC-`, `PXB-`). All arguments are passed to `git log`, so run it inside the
repository. A subject may start with a comma-separated list of keys; one row
is written per key.

Columns: ticket, short hash, subject without the leading key list
(sorted by ticket).

```
git-log-tickets.py release-8.0.40-31..release-8.0.41-32 > commits.csv
git-log-tickets.py release-8.4.9-9..release-8.4.11-11 ^8.0 > commits.csv
```

A commit `PS-11220, PS-11065 [8.4]: OIDC Authentication` gives:

```
"PS-11065","b8e378ecbc3","[8.4]: OIDC Authentication"
"PS-11220","b8e378ecbc3","[8.4]: OIDC Authentication"
```

## jira-ticket.py

Lists JIRA tickets with a given fix version, fetching all result pages.

Columns: key, summary, status, fix versions (`; `-separated), sorted by key.

| Option | Meaning |
|---|---|
| `-f`, `--fix-version` | fix version to search for (required) |
| `-s`, `--status` | only tickets with this status, e.g. `Done` |
| `-m`, `--match PATTERN` | summary condition, can be repeated: `PATTERN` = summary contains, `!PATTERN` = summary does not contain, `''` = no condition. Default: `'!\[doc'` (excludes doc tickets) |

```
jira-ticket.py -f '8.0.41-32 (Q1 2025)' > tickets.csv
jira-ticket.py -f '8.0.41-32 (Q1 2025)' -s Done -m '!\[doc' -m merge > merged.csv
```

Patterns are JIRA text searches (whole words, not substrings). Reserved
characters (`+ - & | ! ( ) { } [ ] ^ ~ * ? \ :`) must be escaped with `\`,
and JIRA ignores them when matching. Put patterns starting with `!` in single
quotes. See `./jira-ticket.py -h` for details.

Environment variables (set before running):

| Variable | Meaning |
|---|---|
| `JIRA_EMAIL` | Atlassian account email (required) |
| `JIRA_TOKEN_FILE` | path to a file containing the API token (takes precedence) |
| `JIRA_TOKEN` | the API token itself (used if `JIRA_TOKEN_FILE` is not set) |

## csv-join.py

Compares two CSV files on their first column and prints the rows that are
present in only one of them, unchanged and in their original order.

```
./csv-join.py <file1> <file2> <join-type>
```

| Join type | Output |
|---|---|
| `outleft` or `l` | rows of file1 whose key does not appear in file2 |
| `outright` or `r` | rows of file2 whose key does not appear in file1 |

## Typical workflow

```
./git-log-tickets.py release-8.0.40-31..release-8.0.41-32 > commits.csv
./jira-ticket.py -f '8.0.41-32 (Q1 2025)' > tickets.csv

# commits whose ticket is not assigned to the fix version
./csv-join.py commits.csv tickets.csv outleft

# tickets assigned to the fix version that have no commit
./csv-join.py commits.csv tickets.csv outright
```
