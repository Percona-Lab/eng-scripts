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
import http.client
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Set

JIRA_SEARCH_URL = "https://perconadev.atlassian.net/rest/api/3/search/jql"
JIRA_MYSELF_URL = "https://perconadev.atlassian.net/rest/api/3/myself"

# Exit code when JIRA rejects the email/token pair.
EXIT_AUTH_FAILED = 3

# Tickets requested per page; all pages are fetched.
PAGE_SIZE = 100

# Seconds to wait for JIRA to connect or send data before giving up.
HTTP_TIMEOUT = 60


# Set by --debug: print diagnostic messages to stderr.
DEBUG = False

# Summary condition used when no --match option is given.
# "[" is a reserved character in JIRA text search, so it is escaped with "\".
DEFAULT_MATCH = r"!\[doc"


def debug(message: str) -> None:
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


class JiraResponseError(RuntimeError):
    """JIRA answered, but not with the JSON object the script expects."""


def read_json_object(response, what: str) -> Dict:
    """Read a response body that must be a JSON object.

    A proxy, SSO login page or maintenance page can answer with HTTP 200 and
    HTML; that is reported as JiraResponseError instead of a traceback.
    """
    raw = response.read()
    content_type = response.headers.get("Content-Type", "-")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        snippet = raw[:300].decode("utf-8", "replace").replace("\n", " ")
        debug(f"{what}: non-JSON response body (first 300 bytes): {snippet}")
        raise JiraResponseError(
            f"{what}: JIRA returned a non-JSON response (HTTP {response.status}, "
            f"Content-Type: {content_type}); a proxy, SSO or maintenance page may be "
            "answering instead of JIRA (run with -d to see the beginning of it)")
    if not isinstance(data, dict):
        raise JiraResponseError(
            f"{what}: expected a JSON object from JIRA, got {type(data).__name__}")
    return data


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
    parser.add_argument("-d", "--debug", action="store_true",
                        help="print debugging information (JQL, URLs, paging) to stderr; "
                             "the API token is never printed")
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
    page = 0
    while True:
        page += 1
        page_params = dict(params)
        if page_token:
            page_params["nextPageToken"] = page_token
        url = f"{JIRA_SEARCH_URL}?{urllib.parse.urlencode(page_params)}"
        debug(f"page {page}: GET {url}")
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                debug(f"page {page}: HTTP {response.status} {response.reason}")
                data = read_json_object(response, f"search page {page}")
        except urllib.error.HTTPError as e:
            if DEBUG:
                # Reading the body can itself fail (e.g. connection reset on a
                # 5xx); that must not replace the HTTPError being re-raised.
                try:
                    body = e.read().decode("utf-8", "replace")
                except Exception as read_error:
                    body = f"<could not read: {type(read_error).__name__}: {read_error}>"
                debug(f"page {page}: HTTP {e.code} {e.reason}, response body: {body}")
            raise

        page_issues = data.get("issues") or []
        if not isinstance(page_issues, list) or not all(isinstance(i, dict) for i in page_issues):
            raise JiraResponseError(f"search page {page}: 'issues' in the JIRA response "
                                    "is not a list of objects")
        issues.extend(page_issues)

        page_token = data.get("nextPageToken")
        # isLast is not always present in the response, so a missing isLast
        # must not end the loop: keep going while there is a nextPageToken.
        is_last = data.get("isLast")
        debug(f"page {page}: {len(page_issues)} issues (total {len(issues)}), "
              f"isLast={is_last}, nextPageToken={page_token!r}")
        if is_last is True or not page_token:
            if is_last is None and not page_token:
                debug("response has neither isLast nor nextPageToken; "
                      "assuming this is the last page")
                # A full page without any paging information is the sign of a
                # known JIRA bug where paging data is dropped although more
                # results exist; the remaining pages cannot be requested.
                if len(page_issues) >= PAGE_SIZE:
                    print(f"Warning: JIRA returned a full page ({len(page_issues)} tickets) "
                          "without isLast or nextPageToken; more tickets may exist and the "
                          "output may be incomplete (run with -d for details)",
                          file=sys.stderr)
            debug(f"done: {len(issues)} issues in {page} page(s)")
            return issues
        if page_token in seen_tokens:
            raise RuntimeError("JIRA returned the same nextPageToken twice")
        seen_tokens.add(page_token)


def verify_auth(email: str, auth: str) -> Optional[str]:
    """Check that JIRA accepts the credentials.

    JIRA treats requests with rejected credentials as anonymous and still
    answers searches with public tickets only, so without this check a bad
    token silently gives incomplete results. Returns an error message, or
    None if authentication works.
    """
    request = urllib.request.Request(
        JIRA_MYSELF_URL,
        headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
    )
    debug(f"GET {JIRA_MYSELF_URL}")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            me = read_json_object(response, "credentials check")
    except urllib.error.HTTPError as e:
        reason = e.headers.get("X-Seraph-LoginReason", "")
        debug(f"HTTP {e.code} {e.reason}, X-Seraph-LoginReason: {reason or '-'}")
        if e.code in (401, 403):
            status = f"HTTP {e.code}, {reason}" if reason else f"HTTP {e.code}"
            if reason == "AUTHENTICATION_DENIED":
                hint = ("JIRA denied login for " + email + " (account may be locked "
                        "after failed attempts); log in via the browser and try again")
            elif e.code == 403:
                hint = ("JIRA denied access for " + email + ". Check that the account "
                        "has permission to access Jira")
            else:
                hint = ("JIRA rejected the API token for " + email + ". Check that the token "
                        "has not expired or been revoked, that it is a regular API token "
                        "(not one 'with scopes'), and that JIRA_EMAIL is the email of the "
                        "Atlassian account the token belongs to. Create a new token at "
                        "https://id.atlassian.com/manage-profile/security/api-tokens")
            return f"authentication failed ({status}): {hint}"
        raise
    debug(f"authenticated as {me.get('displayName')} "
          f"({me.get('emailAddress') or email}, accountId {me.get('accountId')})")
    return None


def main(argv: List[str]) -> int:
    global DEBUG
    args = parse_args(argv)
    DEBUG = args.debug
    prog = os.path.basename(sys.argv[0])
    debug(f"Python {sys.version.split()[0]}")

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
        debug(f"token read from JIRA_TOKEN_FILE={token_file} ({len(token)} characters)")
    else:
        token = os.environ.get("JIRA_TOKEN", "").strip()
        if not token:
            print(f"{prog}: Set JIRA_TOKEN_FILE to the path of a file containing the API token, "
                  "or JIRA_TOKEN to the API token itself", file=sys.stderr)
            return 1
        debug(f"token taken from JIRA_TOKEN ({len(token)} characters)")

    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    jql = build_jql(args.fix_version, args.status, args.match)
    debug(f"JIRA_EMAIL={email}")
    debug(f"JQL: {jql}")
    params = {
        "jql": jql,
        "fields": "key,summary,status,fixVersions",
        "maxResults": PAGE_SIZE,
    }

    try:
        auth_error = verify_auth(email, auth)
        if auth_error:
            print(f"Error: {auth_error}", file=sys.stderr)
            return EXIT_AUTH_FAILED
        issues = fetch_all_issues(params, auth)
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code} {e.reason} from JIRA", file=sys.stderr)
        return 22  # same exit code as curl --fail
    except urllib.error.URLError as e:
        # A connect timeout arrives wrapped in URLError.
        if isinstance(e.reason, socket.timeout):
            print(f"Error: JIRA did not respond within {HTTP_TIMEOUT} seconds (connect timeout)",
                  file=sys.stderr)
        else:
            print(f"Error: cannot reach JIRA: {e.reason}", file=sys.stderr)
        return 1
    except socket.timeout:
        # A read timeout (no data within HTTP_TIMEOUT) is raised as is.
        # socket.timeout is TimeoutError's alias on Python 3.10+.
        print(f"Error: JIRA did not respond within {HTTP_TIMEOUT} seconds (read timeout)",
              file=sys.stderr)
        return 1
    except (http.client.HTTPException, OSError) as e:
        # urllib wraps only errors from sending the request in URLError; a
        # connection dropped while waiting for or reading the response
        # (RemoteDisconnected, ConnectionResetError, IncompleteRead, ...)
        # arrives as is. Must stay after the HTTPError/URLError/timeout
        # clauses, which are subclasses of OSError.
        print(f"Error: connection to JIRA failed: {type(e).__name__}: {e}", file=sys.stderr)
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
