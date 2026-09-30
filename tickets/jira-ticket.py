#!/usr/bin/env python3
"""List JIRA tickets for a given fixVersion, as CSV.

Output columns: key, summary, status, fix versions ("; "-joined).

Environment:
  JIRA_EMAIL       Atlassian account email
  JIRA_TOKEN_FILE  path to a file containing the API token (takes precedence)
  JIRA_TOKEN       the API token itself (used if JIRA_TOKEN_FILE is not set)
"""
import argparse
import base64
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Set

JIRA_SEARCH_URL = "https://perconadev.atlassian.net/rest/api/3/search/jql"

# Tickets requested per page; all pages are fetched.
PAGE_SIZE = 100

# Summary condition used when no --match option is given.
# "[" is a reserved character in JIRA text search, so it is escaped with "\".
DEFAULT_MATCH = r"!\[doc"


def jql_string(value: str) -> str:
    """Quote a value as a JQL string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List JIRA tickets for a fixVersion as CSV.",
        epilog="Examples (all return tickets with the given fix version and fulfilling the additional conditions):\n"
               "  %(prog)s -f '8.0.41-32 (Q1 2025)'\n"
               "       # not matching '[doc' pattern\n"
               "  %(prog)s -f '8.0.41-32 (Q1 2025)' -s Done\n"
               "       # not matching '[doc' pattern, with status 'Done'\n"
               "  %(prog)s -f '8.0.41-32 (Q1 2025)' -m merge\n"
               "       # matching 'merge' pattern\n"
               "  %(prog)s -f '8.0.41-32 (Q1 2025)' -m '!merge'\n"
               "       # not matching 'merge' pattern\n"
               "  %(prog)s -f '8.0.41-32 (Q1 2025)' -m '!\\[doc' -m merge\n"
               "       # not matching '[doc' and matching 'merge'\n"
               "  %(prog)s -f '8.0.41-32 (Q1 2025)' -m ''\n"
               "       # all\n"
               "\n"
               f"Without -m, the default is -m '{DEFAULT_MATCH}'.\n"
               "Use single quotes around patterns starting with '!' (shell history expansion).\n"
               "A leading '\\!' matches a literal '!'.\n"
               "Patterns are JIRA text searches (whole words, not substrings). The characters\n"
               "+ - & | ! ( ) { } [ ] ^ ~ * ? \\ : are reserved: escape them with '\\' (e.g. '\\[doc').\n"
               "JIRA ignores them when matching, so '\\[doc' matches the same as 'doc'.\n"
               "\n"
               "Environment variables:\n"
               "  JIRA_EMAIL       Atlassian account email (required)\n"
               "  JIRA_TOKEN_FILE  path to a file containing the API token (takes precedence)\n"
               "  JIRA_TOKEN       the API token itself (used if JIRA_TOKEN_FILE is not set)\n"
               "Leading and trailing whitespace (including CR/LF) is removed from the token.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-f", "--fix-version", required=True,
                        help="JIRA fixVersion to search for, e.g. '8.0.41-32 (Q1 2025)'")
    parser.add_argument("-s", "--status", default="",
                        help="only tickets with this status, e.g. Done")
    parser.add_argument("-m", "--match", metavar="PATTERN", action="append",
                        help='summary condition, can be repeated: PATTERN adds summary ~ "PATTERN", '
                             '!PATTERN adds summary !~ "PATTERN", an empty PATTERN adds nothing '
                             f"(default: '{DEFAULT_MATCH}')")
    return parser.parse_args(argv)


def summary_condition(pattern: str) -> str:
    """Turn one --match value into a JQL condition ('' for no condition)."""
    if pattern.startswith("!"):
        operator, pattern = "!~", pattern[1:]
    else:
        operator = "~"
        if pattern.startswith("\\!"):
            pattern = pattern[1:]
    if not pattern:
        return ""
    return f"summary {operator} {jql_string(pattern)}"


def build_jql(version: str, status: str, matches: Optional[List[str]]) -> str:
    conditions = [f"fixVersion IN ({jql_string(version)})"]
    if status:
        conditions.append(f"status = {jql_string(status)}")
    for pattern in matches if matches is not None else [DEFAULT_MATCH]:
        condition = summary_condition(pattern)
        if condition:
            conditions.append(condition)
    return " AND ".join(conditions) + " ORDER BY key"


def fetch_all_issues(params: Dict, auth: str) -> List[Dict]:
    """Run the search, following nextPageToken until the last page."""
    issues: List[Dict] = []
    seen_tokens: Set[str] = set()
    page_token = None
    while True:
        page_params = dict(params)
        if page_token:
            page_params["nextPageToken"] = page_token
        request = urllib.request.Request(
            f"{JIRA_SEARCH_URL}?{urllib.parse.urlencode(page_params)}",
            headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            data = json.load(response)

        issues.extend(data.get("issues") or [])

        page_token = data.get("nextPageToken")
        if data.get("isLast", True) or not page_token:
            return issues
        if page_token in seen_tokens:
            raise RuntimeError("JIRA returned the same nextPageToken twice")
        seen_tokens.add(page_token)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    prog = os.path.basename(sys.argv[0])

    email = os.environ.get("JIRA_EMAIL")
    if not email:
        print(f"{prog}: JIRA_EMAIL: Set JIRA_EMAIL to your Atlassian account email", file=sys.stderr)
        return 1
    token_file = os.environ.get("JIRA_TOKEN_FILE")
    if token_file:
        try:
            with open(token_file, encoding="utf-8") as f:
                token = f.read().strip()
        except OSError:
            print(f"Error: cannot read JIRA token file: {token_file}", file=sys.stderr)
            return 1
        if not token:
            print(f"Error: JIRA token file is empty: {token_file}", file=sys.stderr)
            return 1
    else:
        token = os.environ.get("JIRA_TOKEN", "").strip()
        if not token:
            print(f"{prog}: Set JIRA_TOKEN_FILE to the path of a file containing the API token, "
                  "or JIRA_TOKEN to the API token itself", file=sys.stderr)
            return 1

    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    params = {
        "jql": build_jql(args.fix_version, args.status, args.match),
        "fields": "key,summary,status,fixVersions",
        "maxResults": PAGE_SIZE,
    }

    try:
        issues = fetch_all_issues(params, auth)
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code} {e.reason} from JIRA", file=sys.stderr)
        return 22  # same exit code as curl --fail
    except urllib.error.URLError as e:
        print(f"Error: cannot reach JIRA: {e.reason}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    writer = csv.writer(sys.stdout, lineterminator="\n", quoting=csv.QUOTE_ALL)
    for issue in issues:
        fields = issue.get("fields", {})
        writer.writerow([
            issue["key"],
            fields.get("summary") or "",
            (fields.get("status") or {}).get("name") or "",
            "; ".join(v["name"] for v in fields.get("fixVersions") or []),
        ])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
