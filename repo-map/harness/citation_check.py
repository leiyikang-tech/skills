#!/usr/bin/env python3
"""External citation anchor for the repo-map deep-dive.

Verifies a citation's URL actually resolves (arXiv/DOI/wiki/web/github) before
the claim backed by it is trusted as ground truth. This replaces "the LLM
asserts this has paper backing" with a real URL-resolution check.

Exit codes:
  0  resolves
  1  broken / not_found
  2  network error / timeout (leave verify_status as-is in the DB)

Usage:
  citation_check.py --url <url> [--type arxiv|doi|wiki|web|github]
                    [--db {{ANALYSIS_DB}}] [--project <path>]
                    [--concept <id>] [--claim "<text>"]

When --db (or --project/--concept) is given the result is UPSERTed into
deepdive_citations, idempotent on (project_path, concept_id, source_url).

Stdlib only. Redirects are followed via urllib's default RedirectHandler
(up to 5). Proxy env vars (http_proxy/https_proxy) are read naturally by
urllib and are NOT bypassed.
"""

import argparse
import json
import os
import re
import socket
import sqlite3
import sys
import time
import urllib.error
import urllib.request

USER_AGENT = "repo-map-deepdive/1.0 (citation-verifier)"
TIMEOUT = 30  # hard cap, seconds (socket default + per-request)
CHUNK = 512  # small body read for the HEAD->GET fallback, bytes
MAX_STATUS = None  # 429/403 handling below is explicit, not by status range

VALID_STATUS = {"unverified", "resolves", "broken", "not_found"}
VALID_TYPES = {"arxiv", "doi", "wiki", "web", "github"}

# A 403/429 from these hosts is overwhelmingly a bot-block, not a real miss.
# We leave those as 'unverified' rather than condemning a live URL as broken.
BOT_BLOCK_HOSTS = re.compile(
    r"(doi\.org|api\.crossref|scholar\.google|cloudflare|akamai|github\.com)"
)


class Result:
    __slots__ = ("url", "source_type", "status", "final_url", "http_status", "note")

    def __init__(self, url, source_type, status, final_url="", http_status=0, note=""):
        self.url = url
        self.source_type = source_type
        self.status = status
        self.final_url = final_url
        self.http_status = http_status
        self.note = note

    def to_dict(self):
        return {
            "url": self.url,
            "type": self.source_type,
            "status": self.status,
            "final_url": self.final_url,
            "http_status": self.http_status,
            "note": self.note,
        }


def _request(url, method):
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "*/*")
    return req


def _head(url):
    """Return (http_status, final_url, headers) via HEAD."""
    try:
        with urllib.request.urlopen(_request(url, "HEAD"), timeout=TIMEOUT) as resp:
            return resp.status, resp.geturl(), resp.headers
    except urllib.error.HTTPError as e:
        # HTTPError still carries headers/final url (e.g. 405 after redirects).
        return e.code, getattr(e, "url", url) or url, e.headers
    except (urllib.error.URLError, socket.timeout, OSError):
        return None, url, None


def _get_small(url):
    """Return (http_status, final_url) with a GET that reads a small chunk."""
    try:
        with urllib.request.urlopen(_request(url, "GET"), timeout=TIMEOUT) as resp:
            resp.read(CHUNK)  # read-then-close: keep the connection short
            return resp.status, resp.geturl()
    except urllib.error.HTTPError as e:
        return e.code, getattr(e, "url", url) or url
    except (urllib.error.URLError, socket.timeout, OSError):
        return None, url


def resolve(url):
    """Return (status, final_url) with a HEAD-first, GET-fallback strategy.

    HEAD is preferred (cheap, no body). Some servers reject HEAD with 405 or
    bounce it as 403; when the response is not authoritative we fall back to a
    GET that reads only a small chunk. A final 2xx is authoritative.
    """
    # ---- HEAD ----
    code, final, _headers = _head(url)
    if code is not None and 200 <= code < 400:
        return code, final
    # ---- GET fallback on 405/403/429 (HEAD unsupported or bot-bounced) ----
    if code in (405, 403, 429) or code is None:
        gcode, gfinal = _get_small(url)
        if gcode is not None:
            return gcode, gfinal
        return code, final
    # 4xx/5xx from HEAD is authoritative -> no GET needed
    return code, final


def classify(url, source_type, http_status, note=""):
    """Turn a raw http_status into a verify_status per the cross-file contract."""
    if http_status is None:
        return Result(url, source_type, "not_found", note="dns/connection refused")
    if 200 <= http_status < 400:
        return Result(url, source_type, "resolves", http_status=http_status, note=note)
    if http_status in (403, 429) and BOT_BLOCK_HOSTS.search(url):
        # bot-block on a real host: don't condemn it, mark unverified
        return Result(
            url, source_type, "unverified",
            http_status=http_status,
            note=f"possible bot-block (HTTP {http_status})",
        )
    if 400 <= http_status < 600:
        if http_status == 404:
            return Result(
                url, source_type, "not_found", http_status=http_status, note=note
            )
        return Result(url, source_type, "broken", http_status=http_status, note=note)
    return Result(url, source_type, "unverified", http_status=http_status, note=note)


def normalize_arxiv(url):
    """Map an arXiv URL to its canonical abs page. Returns canonical URL or None."""
    m = re.match(r"https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/([^?#]+)", url)
    if m:
        return "https://arxiv.org/abs/" + m.group(1)
    m = re.match(r"https?://(?:www\.)?arxiv\.org/abs/([^?#]+)", url)
    if m:
        return "https://arxiv.org/abs/" + m.group(1)
    return None


def verify_arxiv(url):
    canon = normalize_arxiv(url)
    target = canon or url
    code, final = resolve(target)
    result = classify(target, "arxiv", code)
    if result.status == "resolves" and final and "pdf" in final.lower():
        # abs page redirected to a PDF download -> still resolves
        pass
    result.final_url = final
    return result


def verify_doi(url):
    # resolve() already follows doi.org -> publisher redirects
    code, final = resolve(url)
    result = classify(url, "doi", code)
    result.final_url = final
    return result


def verify_wiki(url):
    code, final = resolve(url)
    result = classify(url, "wiki", code)
    result.final_url = final
    return result


def verify_github(url):
    # env proxy http_proxy=http(s)_proxy=127.0.0.1:8118 handles github
    code, final = resolve(url)
    result = classify(url, "github", code)
    result.final_url = final
    return result


def verify_web(url):
    code, final = resolve(url)
    result = classify(url, "web", code)
    result.final_url = final
    return result


def verify(url, source_type):
    if source_type == "arxiv":
        return verify_arxiv(url)
    if source_type == "doi":
        return verify_doi(url)
    if source_type == "wiki":
        return verify_wiki(url)
    if source_type == "github":
        return verify_github(url)
    return verify_web(url)


def _next_citation_id(con, project_path):
    """Return the next ct-<project>-<n> id for this project."""
    prefix = "ct-"
    base = (project_path or "unknown").replace("/", "-").strip("-") or "proj"
    cursor = con.execute(
        "SELECT citation_id FROM deepdive_citations WHERE citation_id LIKE ? ORDER BY citation_id DESC LIMIT 1",
        (f"ct-{base}-%",),
    )
    row = cursor.fetchone()
    if row:
        try:
            n = int(row[0].rsplit("-", 1)[-1]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"{prefix}{base}-{n}"


def upsert(db_path, project_path, concept_id, claim, url, source_type, result):
    """Idempotently write the verification result into deepdive_citations."""
    if not db_path:
        return
    con = None
    try:
        con = sqlite3.connect(db_path, timeout=10)
        con.execute("PRAGMA busy_timeout = 10000")
        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            "SELECT citation_id FROM deepdive_citations "
            "WHERE project_path=? AND concept_id=? AND source_url=?",
            (project_path, concept_id, url),
        )
        existing = cur.fetchone()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        url_verified = 1 if result.status == "resolves" else 0
        if existing:
            con.execute(
                "UPDATE deepdive_citations SET claim=?, source_type=?, "
                "url_verified=?, verify_status=?, verified_at=? WHERE citation_id=?",
                (claim, source_type, url_verified, result.status, now, existing[0]),
            )
        else:
            citation_id = _next_citation_id(con, project_path)
            con.execute(
                "INSERT INTO deepdive_citations "
                "(citation_id, project_path, concept_id, claim, source_url, "
                " source_type, url_verified, verify_status, verified_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    citation_id,
                    project_path,
                    concept_id,
                    claim,
                    url,
                    source_type,
                    url_verified,
                    result.status,
                    now,
                ),
            )
        con.commit()
    except sqlite3.Error as e:
        if con is not None:
            try:
                con.rollback()
            except sqlite3.Error:
                pass
        sys.stderr.write(f"citation_check: DB write failed: {e}\n")
    finally:
        if con is not None:
            con.close()


def main():
    parser = argparse.ArgumentParser(
        description="Verify a citation URL resolves before trusting the claim."
    )
    parser.add_argument("--url", required=True, help="citation URL to verify")
    parser.add_argument(
        "--type",
        dest="source_type",
        default="web",
        choices=sorted(VALID_TYPES),
        help="citation type (default: web)",
    )
    parser.add_argument(
        "--db", default=os.path.expanduser("{{ANALYSIS_DB}}"),
        help="board analysis.db path (default: {{ANALYSIS_DB}})",
    )
    parser.add_argument("--project", help="project_path for the citation record")
    parser.add_argument("--concept", help="concept_id for the citation record")
    parser.add_argument("--claim", default="", help="claim text the citation backs")
    args = parser.parse_args()

    socket.setdefaulttimeout(TIMEOUT)

    result = verify(args.url, args.source_type)

    # Exit semantics: 0 resolves, 1 broken/not_found, 2 network/timeout
    if result.status == "resolves":
        code = 0
    elif result.status in ("broken", "not_found"):
        code = 1
    else:  # unverified (timeout / bot-block)
        code = 2

    # Persist only when a project/concept/db target was supplied.
    if args.project or args.concept or args.db:
        upsert(
            args.db,
            args.project or "",
            args.concept or "",
            args.claim,
            args.url,
            args.source_type,
            result,
        )

    print(json.dumps(result.to_dict(), ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())