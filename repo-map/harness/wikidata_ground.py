#!/usr/bin/env python3
"""Ground a concept name to a canonical Wikidata QID via SPARQL.

This is the EXTERNAL-ANCHOR mechanism for the deep-dive: it replaces "the LLM
claims this concept maps to Wikipedia page X" with a real resolver that returns
a QID or fails. The output contract here is the grounding_status enum that
deep-dive's playbook reads:

  grounded     - an entity whose label EXACTLY equals the concept (best)
  partial      - only a fuzzy/substring label match found
  not_found    - no entity matched the concept
  hallucination- concept looks like a generic/vague flag, not a groundable name
                 (short names, or generic {abstract,framework,method,...} terms)

Exit codes (deterministic, matching the gates.py style):
  0 = grounded | partial      (a usable QID was resolved)
  1 = not_found | hallucination (no usable grounding)
  2 = network / SPARQL error   (retryable, infrastructure problem)

Stdlib only. Query goes to https://query.wikidata.org/sparql with a required
User-Agent. The environment may route through a local proxy
(http_proxy=http://127.0.0.1:8118), so a hard socket timeout is set to avoid
hanging.

  wikidata_ground.py --concept "<name>" [--lang en] [--db {{ANALYSIS_DB}}] [--project <path>]
"""

import argparse
import json
import re
import socket
import sqlite3
import sys
import urllib.parse
import urllib.request

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "repo-map-deepdive/1.0 (grounding client)"
HTTP_TIMEOUT = 30  # seconds; socket default + per-request timeout

# Generic terms that are not groundable concepts. A concept that is exactly one
# of these (case-insensitive) is flagged hallucination. Keep this tiny per the
# spec - the heuristic is a safety net, not a taxonomy.
GENERIC_TERMS = {
    "abstract", "abstraction", "architecture", "approach", "concept",
    "framework", "idea", "method", "methodology", "model", "pattern",
    "principle", "strategy", "technique", "the", "theory", "tool",
}


def _http_get_json(url):
    """GET a SPARQL endpoint and parse its JSON result. Returns (rows, None) or
    (None, error_msg). Raises no exceptions."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = resp.read()
        payload = json.loads(data.decode("utf-8"))
        rows = payload.get("results", {}).get("bindings", [])
        return rows, None
    except Exception as e:  # noqa: BLE001 - any URLError/HTTPError/parse error is a network failure
        return None, str(e)


def _qid(binding):
    return (binding.get("entity") or {}).get("value", "")


def _label(binding):
    return (binding.get("entityLabel") or {}).get("value", "")


def _sitelink(binding):
    return (binding.get("sitelink") or {}).get("value", "")


def _lang_filter_expr(lang):
    """The FILTER(LANG(...) = '<lang>') expression. Guard against quote injection."""
    return re.sub(r"[^a-zA-Z0-9_-]", "", lang) or "en"


def query_wikidata(concept, lang):
    """Run SPARQL against Wikidata. Returns (rows, None) or (None, err)."""
    clang = _lang_filter_expr(lang)
    # SELECT ... WHERE { ?entity rdfs:label ?entityLabel . FILTER(LANG(?entityLabel) = "<clang>")
    #   FILTER(CONTAINS(LCASE(?entityLabel), LCASE("<concept>")))
    #   OPTIONAL { ?sitelink schema:about ?entity ; schema:isPartOf <https://en.wikipedia.org/> }
    #   SERVICE wikibase:label { bd:serviceParam wikibase:language "<clang>,en" } } LIMIT 5
    inner = (
        "?entity rdfs:label ?entityLabel . "
        "FILTER(LANG(?entityLabel) = \"{lang}\") . "
        "FILTER(CONTAINS(LCASE(?entityLabel), LCASE(\"{concept}\"))) "
        "OPTIONAL {{ ?sitelink schema:about ?entity ; schema:isPartOf <https://en.wikipedia.org/> }} "
        "SERVICE wikibase:label {{ bd:serviceParam wikibase:language \"{lang},en\" }}"
    ).format(lang=clang, concept=concept.replace('"', '\\"'))
    query = "SELECT ?entity ?entityLabel ?sitelink WHERE {{ {inner} }} LIMIT 5".format(inner=inner)
    url = SPARQL_ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    return _http_get_json(url)


def _exact_vs_fuzzy(rows, concept, lang):
    """Pick the best binding. Prefer a QID whose label EXACTLY equals the concept
    (case-insensitive); otherwise fall back to the first fuzzy/substring match.

    Returns (qid, label, sitelink, is_exact)."""
    concept_lc = concept.lower()
    for b in rows:
        if _label(b).lower() == concept_lc:
            return _qid(b), _label(b), _sitelink(b), True
    # fuzzy: return the best partial match (first; results are not ranked)
    for b in rows:
        lbl = _label(b)
        if lbl:
            return _qid(b), lbl, _sitelink(b), False
    return "", "", "", False


def classify(concept, qid, is_exact, lang):
    """Map a grounding attempt to the grounding_status enum contract.

    hallucination = generic/short name that can never be a real Wikidata anchor.
    grounded      = exact label match resolved to a QID.
    partial       = only fuzzy/substring match resolved.
    not_found     = name looked groundable but no entity came back."""
    name_lc = concept.lower().strip()
    if len(name_lc) < 3 or name_lc in GENERIC_TERMS:
        return "hallucination"
    if not qid:
        return "not_found"
    return "grounded" if is_exact else "partial"


def upsert(con, project, concept, qid, label, url, status):
    """UPSERT a grounding record into deepdive_concepts. Idempotent: if the
    concept name already exists for this project, UPDATE instead of INSERT.
    concept_id = cc-<sanitized-project>-<n> where n is a per-project sequence.

    Uses the concurrency contract from deepdive.sql: BEGIN IMMEDIATE + busy_timeout
    so parallel deep-dive processes don't corrupt the sequence counter."""
    con.execute("PRAGMA busy_timeout = 10000")
    con.execute("BEGIN IMMEDIATE")
    try:
        cur = con.execute(
            "SELECT concept_id FROM deepdive_concepts WHERE project_path = ? AND name = ?",
            (project, concept),
        )
        row = cur.fetchone()
        if row:
            con.execute(
                """UPDATE deepdive_concepts
                   SET wiki_qid = ?, wiki_label = ?, wiki_url = ?, grounding_status = ?
                   WHERE concept_id = ?""",
                (qid, label, url, status, row[0]),
            )
            cid = row[0]
        else:
            # compute the next sequence number for this project
            cur = con.execute(
                "SELECT concept_id FROM deepdive_concepts WHERE project_path = ? ORDER BY concept_id DESC LIMIT 1",
                (project,),
            )
            prev = cur.fetchone()
            n = 1
            if prev:
                m = re.search(r"-(\d+)$", prev[0])
                if m:
                    n = int(m.group(1)) + 1
            safe = re.sub(r"[^A-Za-z0-9_-]", "-", project).strip("-") or "project"
            cid = "cc-{}-{}".format(safe, n)
            con.execute(
                """INSERT INTO deepdive_concepts
                       (concept_id, project_path, name, wiki_qid, wiki_label, wiki_url, grounding_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cid, project, concept, qid, label, url, status),
            )
        con.commit()
        return cid
    except Exception:
        con.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description="ground a concept to a canonical Wikidata QID via SPARQL")
    parser.add_argument("--concept", required=True, help="concept name to ground")
    parser.add_argument("--lang", default="en", help="SPARQL label language (default: en)")
    parser.add_argument("--db", help="path to the analysis.sqlite DB for upsert")
    parser.add_argument("--project", help="project path; required with --db for upsert")
    args = parser.parse_args()

    concept = args.concept.strip()
    if not concept:
        print(json.dumps({"concept": args.concept, "qid": "", "label": "", "url": "",
                          "grounding_status": "hallucination", "source": "local-heuristic"}))
        return 1

    # Set a socket default timeout so even a path that bypasses urlopen's timeout
    # (e.g. proxy connect) cannot hang indefinitely.
    socket.setdefaulttimeout(HTTP_TIMEOUT)

    rows, err = query_wikidata(concept, args.lang)
    if err is not None:
        print("wikidata_ground: SPARQL/network error: {}".format(err), file=sys.stderr)
        return 2

    qid, label, sitelink, is_exact = _exact_vs_fuzzy(rows, concept, args.lang)
    status = classify(concept, qid, is_exact, args.lang)

    # Only trust a partial/fuzzy label if the entity label is non-empty and the
    # match actually contains the concept. not_found means no rows at all.
    if status == "partial" and not label:
        status = "not_found"

    url = sitelink if sitelink.startswith("http") else ("https://www.wikidata.org/wiki/" + qid if qid else "")
    source = "sparql-exact" if is_exact and qid else ("sparql-fuzzy" if qid else ("local-heuristic" if status == "hallucination" else "sparql-none"))

    result = {
        "concept": concept,
        "qid": qid,
        "label": label,
        "url": url,
        "grounding_status": status,
        "source": source,
    }
    print(json.dumps(result))

    if args.db and args.project:
        con = sqlite3.connect(args.db, timeout=10)
        try:
            cid = upsert(con, args.project, concept, qid, label, url, status)
            result["concept_id"] = cid
            print(json.dumps({"upserted": cid, "grounding_status": status, "concept_id": cid}))
        except Exception as e:  # noqa: BLE001 - DB failure is reported but not a network exit(2)
            print("wikidata_ground: DB upsert error: {}".format(e), file=sys.stderr)
            return 2
        finally:
            con.close()

    # Exit code mirrors the grounding contract: usable anchor (0) vs no anchor (1)
    # vs infrastructure/DB failure (2).
    return 0 if status in ("grounded", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())